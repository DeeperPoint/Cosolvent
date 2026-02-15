function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function flatten(value, prefix = "", out = {}) {
  if (Array.isArray(value)) {
    value.forEach((item, idx) => {
      flatten(item, prefix ? `${prefix}.${idx}` : String(idx), out);
    });
    return out;
  }
  if (isObject(value)) {
    Object.keys(value).forEach((key) => {
      flatten(value[key], prefix ? `${prefix}.${key}` : key, out);
    });
    return out;
  }
  out[prefix] = value;
  return out;
}

function groupForPath(path) {
  if (path.startsWith("participant_types")) {
    return "Roles";
  }
  if (path.startsWith("onboarding")) {
    return "Onboarding";
  }
  if (path.startsWith("communication")) {
    return "Communication";
  }
  if (path.startsWith("profile_schemas")) {
    return "Profile Schema";
  }
  if (path.startsWith("discovery")) {
    return "Discovery";
  }
  if (path.startsWith("marketplace")) {
    return "Marketplace Basics";
  }
  return "Other";
}

function isDestructive(path, kind) {
  if (kind === "removed" && path.includes("participant_types")) {
    return true;
  }
  if (path.includes(".slug") || path.includes("profile_schemas")) {
    return true;
  }
  return false;
}

export function buildConfigDiff(before, after) {
  const beforeFlat = flatten(before || {});
  const afterFlat = flatten(after || {});
  const allKeys = new Set([...Object.keys(beforeFlat), ...Object.keys(afterFlat)]);

  const groups = {};
  let destructiveCount = 0;
  for (const key of Array.from(allKeys).sort()) {
    const beforeHas = Object.prototype.hasOwnProperty.call(beforeFlat, key);
    const afterHas = Object.prototype.hasOwnProperty.call(afterFlat, key);
    const beforeValue = beforeFlat[key];
    const afterValue = afterFlat[key];
    let kind = null;
    if (!beforeHas && afterHas) {
      kind = "added";
    } else if (beforeHas && !afterHas) {
      kind = "removed";
    } else if (JSON.stringify(beforeValue) !== JSON.stringify(afterValue)) {
      kind = "changed";
    }
    if (!kind) {
      continue;
    }
    const section = groupForPath(key);
    if (!groups[section]) {
      groups[section] = [];
    }
    const destructive = isDestructive(key, kind);
    if (destructive) {
      destructiveCount += 1;
    }
    groups[section].push({
      path: key,
      kind,
      beforeValue,
      afterValue,
      destructive,
    });
  }
  return { groups, destructiveCount };
}

function pretty(value) {
  if (value === undefined) {
    return "undefined";
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return `"${value}"`;
  }
  return JSON.stringify(value);
}

export function renderDiffHtml(diff) {
  const sections = Object.keys(diff.groups);
  if (sections.length === 0) {
    return "<p>No semantic changes detected.</p>";
  }
  return sections
    .map((section) => {
      const items = diff.groups[section]
        .map((item) => {
          const marker = item.kind === "added" ? "+" : item.kind === "removed" ? "-" : "~";
          const details =
            item.kind === "changed"
              ? `${pretty(item.beforeValue)} -> ${pretty(item.afterValue)}`
              : item.kind === "added"
                ? `new ${pretty(item.afterValue)}`
                : `removed ${pretty(item.beforeValue)}`;
          return `<li class="${item.destructive ? "destructive" : ""}">
            <span>${marker} ${item.path}</span>
            <div class="small-mono">${details}</div>
          </li>`;
        })
        .join("");
      return `<section><strong>${section}</strong><ul>${items}</ul></section>`;
    })
    .join("");
}
