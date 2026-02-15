const MESSAGE_REWRITES = [
  {
    match: "At least 2 participant types required",
    friendly: "Add at least two roles. A marketplace needs both sides to match.",
    stepIndex: 2,
  },
  {
    match: "At least one participant type must have can_search=true",
    friendly: "Enable search for at least one role so users can discover profiles.",
    stepIndex: 2,
  },
  {
    match: "At least one participant type must have visible_in_search=true",
    friendly: "At least one role must be visible in search results.",
    stepIndex: 2,
  },
  {
    match: "Missing onboarding config",
    friendly: "Each role needs onboarding rules.",
    stepIndex: 3,
  },
  {
    match: "Conversation rule references unknown",
    friendly: "One communication rule references a role that does not exist.",
    stepIndex: 4,
  },
  {
    match: "Discovery searchable_types references unknown",
    friendly: "One searchable role is invalid. Re-check discovery role selections.",
    stepIndex: 5,
  },
  {
    match: "Discovery filter_field",
    friendly: "A discovery filter field does not exist in any profile schema.",
    stepIndex: 5,
  },
];

function stepFromPath(path) {
  if (!path) {
    return 6;
  }
  if (path.startsWith("marketplace.")) {
    return 1;
  }
  if (path.startsWith("participant_types")) {
    return 2;
  }
  if (path.startsWith("onboarding.")) {
    return 3;
  }
  if (path.startsWith("communication.")) {
    return 4;
  }
  if (path.startsWith("profile_schemas.") || path.startsWith("discovery.")) {
    return 5;
  }
  return 6;
}

function joinLoc(loc) {
  if (!Array.isArray(loc)) {
    return "";
  }
  if (loc.length > 0 && loc[0] === "config") {
    return loc.slice(1).join(".");
  }
  return loc.join(".");
}

export function mapValidationErrors(errors) {
  if (!Array.isArray(errors)) {
    return [];
  }
  return errors.map((error) => {
    const path = joinLoc(error?.loc);
    const msg = String(error?.msg || "Validation error");
    const rewrite = MESSAGE_REWRITES.find((item) => msg.includes(item.match));
    return {
      path,
      stepIndex: rewrite ? rewrite.stepIndex : stepFromPath(path),
      message: rewrite ? rewrite.friendly : msg,
      rawMessage: msg,
    };
  });
}
