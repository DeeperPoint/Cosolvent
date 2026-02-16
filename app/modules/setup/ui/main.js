import { DESIGN_TOKENS } from "./tokens.js";
import { GLOSSARY_TERMS, getFieldHelp, listHelpEntries } from "./help-content.js";
import { STEPS } from "./steps.js";
import { mapValidationErrors } from "./validation-mapper.js";
import { buildConfigDiff, renderDiffHtml } from "./diff-renderer.js";
import {
  clone,
  createParticipant,
  currentSlugs,
  defaultField,
  defaultSection,
  fallbackConfig,
  htmlEscape,
  normalizeConfig,
  setAtPath,
  updateSlugReferences,
} from "./state-utils.js";

let configState = fallbackConfig();
let activeStep = 0;
let advancedMode = false;
let sourcePath = "";
let presets = [];
let lastValidatedConfig = null;
let latestJsonDiff = null;
let jsonDraftConfig = null;
let jsonDraftValid = false;
let jsonValidationTimer = null;

const dom = {
  sourcePath: document.getElementById("sourcePath"),
  statusLine: document.getElementById("statusLine"),
  stepNav: document.getElementById("stepNav"),
  stepPanels: Array.from(document.querySelectorAll(".step-panel")),
  prevStepBtn: document.getElementById("prevStepBtn"),
  nextStepBtn: document.getElementById("nextStepBtn"),
  friendlyErrors: document.getElementById("friendlyErrors"),
  presetList: document.getElementById("presetList"),
  quickReadiness: document.getElementById("quickReadiness"),
  quickLaunchStyle: document.getElementById("quickLaunchStyle"),
  marketplaceName: document.getElementById("marketplaceName"),
  marketplaceDescription: document.getElementById("marketplaceDescription"),
  marketplaceIndustry: document.getElementById("marketplaceIndustry"),
  participantList: document.getElementById("participantList"),
  onboardingList: document.getElementById("onboardingList"),
  ruleList: document.getElementById("ruleList"),
  searchableTypes: document.getElementById("searchableTypes"),
  filterFieldsInput: document.getElementById("filterFieldsInput"),
  anonymousVisibility: document.getElementById("anonymousVisibility"),
  authenticatedVisibility: document.getElementById("authenticatedVisibility"),
  anonymousSearchEnabled: document.getElementById("anonymousSearchEnabled"),
  anonymousFilterMode: document.getElementById("anonymousFilterMode"),
  vectorSearchEnabled: document.getElementById("vectorSearchEnabled"),
  ragQueryEnabled: document.getElementById("ragQueryEnabled"),
  followUpSuggestions: document.getElementById("followUpSuggestions"),
  profileRetrievalMode: document.getElementById("profileRetrievalMode"),
  ragFailureBehavior: document.getElementById("ragFailureBehavior"),
  profileSimilarityThreshold: document.getElementById("profileSimilarityThreshold"),
  maxVectorCandidates: document.getElementById("maxVectorCandidates"),
  schemaList: document.getElementById("schemaList"),
  riskList: document.getElementById("riskList"),
  yamlPreview: document.getElementById("yamlPreview"),
  generateReport: document.getElementById("generateReport"),
  outputPathInput: document.getElementById("outputPathInput"),
  applyRuntimeInput: document.getElementById("applyRuntimeInput"),
  compileModeInput: document.getElementById("compileModeInput"),
  exportDirInput: document.getElementById("exportDirInput"),
  exportEnabledInput: document.getElementById("exportEnabledInput"),
  advancedPanel: document.getElementById("advancedPanel"),
  guidedModeBtn: document.getElementById("guidedModeBtn"),
  advancedModeBtn: document.getElementById("advancedModeBtn"),
  jsonEditor: document.getElementById("jsonEditor"),
  jsonStatus: document.getElementById("jsonStatus"),
  formatJsonBtn: document.getElementById("formatJsonBtn"),
  applyJsonBtn: document.getElementById("applyJsonBtn"),
  jsonDiff: document.getElementById("jsonDiff"),
  glossaryDrawer: document.getElementById("glossaryDrawer"),
  glossaryList: document.getElementById("glossaryList"),
  glossarySearchInput: document.getElementById("glossarySearchInput"),
  openGlossaryBtn: document.getElementById("openGlossaryBtn"),
  closeGlossaryBtn: document.getElementById("closeGlossaryBtn"),
  helpPopover: document.getElementById("helpPopover"),
  loadConfigBtn: document.getElementById("loadConfigBtn"),
  validateBtn: document.getElementById("validateBtn"),
  renderYamlBtn: document.getElementById("renderYamlBtn"),
  addParticipantBtn: document.getElementById("addParticipantBtn"),
  addRuleBtn: document.getElementById("addRuleBtn"),
  saveBtn: document.getElementById("saveBtn"),
  checkGeneratedBtn: document.getElementById("checkGeneratedBtn"),
  generateBtn: document.getElementById("generateBtn"),
};

function setStatus(kind, message) {
  dom.statusLine.textContent = message;
  dom.statusLine.dataset.kind = kind || "";
}

function maybeReduceMotion() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.documentElement.style.setProperty("--motion-fast", "0ms");
  } else {
    document.documentElement.style.setProperty("--motion-fast", `${DESIGN_TOKENS.motion.fast}ms`);
  }
}

function helpButton(path) {
  return `<button type="button" class="help-dot" data-help-path="${htmlEscape(path)}" aria-label="Help for ${htmlEscape(path)}">?</button>`;
}

function renderStepNav() {
  const completion = computeStepCompletion();
  dom.stepNav.innerHTML = STEPS.map((step, idx) => {
    const cls = ["step-item"];
    if (idx === activeStep) {
      cls.push("active");
    }
    if (completion[idx].done) {
      cls.push("done");
    }
    return `<li><button type="button" class="${cls.join(" ")}" data-step-nav="${idx}">${idx + 1}. ${htmlEscape(step.title)}</button></li>`;
  }).join("");
}

function renderStepPanels() {
  dom.stepPanels.forEach((panel, idx) => {
    panel.classList.toggle("hidden", idx !== activeStep);
  });
  dom.prevStepBtn.disabled = activeStep === 0;
  dom.nextStepBtn.textContent = activeStep === STEPS.length - 1 ? "Stay on Review" : "Next";
}

function computeStepCompletion() {
  const slugs = currentSlugs(configState);
  const completion = [];
  completion[0] = { done: Boolean(presets.length) };
  completion[1] = {
    done:
      Boolean(configState.marketplace?.name?.trim()) &&
      Boolean(configState.marketplace?.industry?.trim()) &&
      Boolean(configState.marketplace?.description?.trim()),
  };
  completion[2] = {
    done:
      Array.isArray(configState.participant_types) &&
      configState.participant_types.length >= 2 &&
      new Set(slugs).size === slugs.length &&
      configState.participant_types.every((pt) => pt.name && pt.slug),
  };
  completion[3] = {
    done: slugs.every((slug) => Boolean(configState.onboarding[slug])),
  };
  completion[4] = {
    done: Array.isArray(configState.communication.conversation_rules) && configState.communication.conversation_rules.length > 0,
  };
  completion[5] = {
    done:
      slugs.every((slug) => (configState.profile_schemas[slug]?.sections || []).length > 0) &&
      Array.isArray(configState.discovery.searchable_types),
  };
  completion[6] = {
    done: completion.slice(1, 6).every((item) => item.done),
  };
  return completion;
}

function setActiveStep(stepIndex) {
  activeStep = Math.max(0, Math.min(STEPS.length - 1, stepIndex));
  renderAll();
}

function renderPresetList() {
  dom.presetList.innerHTML = presets
    .map(
      (preset) => `
      <article class="preset-card">
        <h3>${htmlEscape(preset.title)}</h3>
        <p>${htmlEscape(preset.description)}</p>
        <p class="small">${htmlEscape(preset.when_to_use)}</p>
        <button type="button" class="outline-btn" data-action="apply-preset" data-preset-id="${htmlEscape(preset.id)}">
          Use this template
        </button>
      </article>
    `,
    )
    .join("");
}

function renderBasics() {
  dom.marketplaceName.value = configState.marketplace.name || "";
  dom.marketplaceDescription.value = configState.marketplace.description || "";
  dom.marketplaceIndustry.value = configState.marketplace.industry || "";
}

function renderParticipants() {
  const permissionRows = [
    ["can_list", "Can publish listings", "participant_types.*.permissions.can_list"],
    ["can_search", "Can search profiles", "participant_types.*.permissions.can_search"],
    ["can_initiate_conversation", "Can start conversations", "participant_types.*.permissions.can_initiate_conversation"],
    ["can_receive_conversation", "Can receive conversations", "participant_types.*.permissions.can_receive_conversation"],
    ["can_share_private_assets", "Can share private files", "participant_types.*.permissions.can_share_private_assets"],
    ["requires_onboarding", "Must complete onboarding", "participant_types.*.permissions.requires_onboarding"],
    ["requires_approval", "Needs approval before active", "participant_types.*.permissions.requires_approval"],
    ["visible_in_search", "Visible in search", "participant_types.*.permissions.visible_in_search"],
  ];
  dom.participantList.innerHTML = configState.participant_types
    .map((pt, idx) => {
      const checks = permissionRows
        .map(
          ([key, label, helpPath]) => `
          <label>
            <input data-bind="participant_types.${idx}.permissions.${key}" type="checkbox" ${pt.permissions[key] ? "checked" : ""} />
            ${htmlEscape(label)} ${helpButton(helpPath)}
          </label>
        `,
        )
        .join("");
      return `
      <article class="role-card">
        <div class="role-title">
          <h3>${htmlEscape(pt.name || `Role ${idx + 1}`)}</h3>
          <button class="outline-btn" type="button" data-action="remove-participant" data-index="${idx}">Remove Role</button>
        </div>
        <div class="grid-3">
          <label class="field">
            <span class="field-help">Role name ${helpButton(`participant_types.${idx}.name`)}</span>
            <input data-bind="participant_types.${idx}.name" type="text" value="${htmlEscape(pt.name)}" />
          </label>
          <label class="field">
            <span class="field-help">Role slug ${helpButton(`participant_types.${idx}.slug`)}</span>
            <input data-bind="participant_types.${idx}.slug" data-slug-input="true" type="text" value="${htmlEscape(pt.slug)}" />
          </label>
          <label class="field">
            <span class="field-help">Role type ${helpButton(`participant_types.${idx}.role`)}</span>
            <select data-bind="participant_types.${idx}.role">
              <option value="supply" ${pt.role === "supply" ? "selected" : ""}>Supply-side</option>
              <option value="demand" ${pt.role === "demand" ? "selected" : ""}>Demand-side</option>
              <option value="facilitator" ${pt.role === "facilitator" ? "selected" : ""}>Facilitator</option>
            </select>
          </label>
        </div>
        <p class="help-note">Recommendation: keep 2 to 3 roles for MVP launch clarity.</p>
        <div class="check-grid">${checks}</div>
      </article>
    `;
    })
    .join("");
}

function renderOnboarding() {
  dom.onboardingList.innerHTML = configState.participant_types
    .map((pt) => {
      const ob = configState.onboarding[pt.slug];
      return `
      <article class="onboarding-card">
        <h3>${htmlEscape(pt.name)} onboarding policy</h3>
        <div class="grid-3">
          <label class="checkline">
            <input data-bind="onboarding.${pt.slug}.requires_approval" type="checkbox" ${ob.requires_approval ? "checked" : ""} />
            Require admin approval ${helpButton(`onboarding.${pt.slug}.requires_approval`)}
          </label>
          <label class="field">
            <span class="field-help">Approval style ${helpButton(`onboarding.${pt.slug}.approval_type`)}</span>
            <select data-bind="onboarding.${pt.slug}.approval_type">
              <option value="manual" ${ob.approval_type === "manual" ? "selected" : ""}>Manual review</option>
              <option value="auto" ${ob.approval_type === "auto" ? "selected" : ""}>Auto approve</option>
            </select>
          </label>
          <label class="field">
            <span class="field-help">Minimum profile completeness (%) ${helpButton(`onboarding.${pt.slug}.profile_completeness_threshold`)}</span>
            <input data-bind="onboarding.${pt.slug}.profile_completeness_threshold" type="number" min="0" max="100" value="${Number(ob.profile_completeness_threshold ?? 100)}" />
          </label>
        </div>
        <details class="advanced-block">
          <summary>Advanced onboarding options</summary>
          <div class="checks">
            <label><input data-bind="onboarding.${pt.slug}.document_upload_required" type="checkbox" ${ob.document_upload_required ? "checked" : ""} /> Require documents on onboarding</label>
            <label><input data-bind="onboarding.${pt.slug}.ai_extraction_enabled" type="checkbox" ${ob.ai_extraction_enabled ? "checked" : ""} /> Enable AI extraction from documents</label>
            <label><input data-bind="onboarding.${pt.slug}.ai_profile_generation" type="checkbox" ${ob.ai_profile_generation ? "checked" : ""} /> Enable AI profile drafts</label>
            <label><input data-bind="onboarding.${pt.slug}.welcome_email_on_approval" type="checkbox" ${ob.welcome_email_on_approval ? "checked" : ""} /> Send welcome email when approved</label>
          </div>
        </details>
      </article>
    `;
    })
    .join("");
}

function renderCommunication() {
  const slugs = currentSlugs(configState);
  dom.ruleList.innerHTML = configState.communication.conversation_rules
    .map(
      (rule, idx) => `
      <article class="rule-card">
        <div class="role-title">
          <h3>Rule ${idx + 1}</h3>
          <button class="outline-btn" type="button" data-action="remove-rule" data-index="${idx}">Remove Rule</button>
        </div>
        <div class="grid-3">
          <label class="field">
            <span>Who can initiate</span>
            <select data-bind="communication.conversation_rules.${idx}.initiator">
              ${slugs.map((slug) => `<option value="${htmlEscape(slug)}" ${slug === rule.initiator ? "selected" : ""}>${htmlEscape(slug)}</option>`).join("")}
            </select>
          </label>
          <label class="field">
            <span>Who receives requests</span>
            <select data-bind="communication.conversation_rules.${idx}.receiver">
              ${slugs.map((slug) => `<option value="${htmlEscape(slug)}" ${slug === rule.receiver ? "selected" : ""}>${htmlEscape(slug)}</option>`).join("")}
            </select>
          </label>
          <label class="checkline">
            <input data-bind="communication.conversation_rules.${idx}.requires_approval" type="checkbox" ${rule.requires_approval ? "checked" : ""} />
            Request requires approval
          </label>
        </div>
      </article>
    `,
    )
    .join("");
}

function renderDiscovery() {
  const slugs = currentSlugs(configState);
  dom.searchableTypes.innerHTML = slugs
    .map(
      (slug) => `
      <label><input type="checkbox" data-searchable-type="${htmlEscape(slug)}" ${configState.discovery.searchable_types.includes(slug) ? "checked" : ""} /> ${htmlEscape(slug)}</label>
    `,
    )
    .join("");
  dom.filterFieldsInput.value = configState.discovery.filter_fields.join(", ");
  dom.anonymousVisibility.value = configState.discovery.result_visibility.anonymous;
  dom.authenticatedVisibility.value = configState.discovery.result_visibility.authenticated;
  dom.anonymousSearchEnabled.checked = Boolean(configState.discovery.access.anonymous_search_enabled);
  dom.anonymousFilterMode.value = configState.discovery.access.anonymous_filter_mode;
  dom.vectorSearchEnabled.checked = Boolean(configState.discovery.ai.vector_search_enabled);
  dom.ragQueryEnabled.checked = Boolean(configState.discovery.ai.rag_query_enabled);
  dom.followUpSuggestions.checked = Boolean(configState.discovery.ai.follow_up_suggestions);
  dom.profileRetrievalMode.value = configState.discovery.ai.profile_retrieval_mode;
  dom.ragFailureBehavior.value = configState.discovery.ai.rag_failure_behavior;
  dom.profileSimilarityThreshold.value = String(configState.discovery.ai.profile_similarity_threshold);
  dom.maxVectorCandidates.value = String(configState.discovery.ai.max_vector_candidates);
}

function fieldTypeOptions(selected) {
  const types = ["text", "number", "select", "multi_select", "date", "file", "rich_text", "location"];
  return types
    .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`)
    .join("");
}

function fieldVisibilityOptions(selected) {
  const values = ["public", "protected", "private"];
  return values
    .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`)
    .join("");
}

function renderSchemas() {
  dom.schemaList.innerHTML = configState.participant_types
    .map((pt) => {
      const schema = configState.profile_schemas[pt.slug] || { sections: [] };
      const sections = schema.sections || [];
      return `
      <article class="schema-card">
        <div class="section-head">
          <h3>${htmlEscape(pt.name)} profile fields</h3>
          <button class="outline-btn" type="button" data-action="add-section" data-slug="${htmlEscape(pt.slug)}">Add Section</button>
        </div>
        ${sections
          .map(
            (section, sIndex) => `
          <section class="field-chip">
            <div class="field-chip-head">
              <h5>Section ${sIndex + 1}</h5>
              <div class="small-mono">${htmlEscape(pt.slug)}</div>
            </div>
            <div class="grid-2">
              <label class="field">
                <span>Section name</span>
                <input data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.name" type="text" value="${htmlEscape(section.name)}" />
              </label>
              <div class="field">
                <span>Section actions</span>
                <button class="outline-btn" type="button" data-action="remove-section" data-slug="${htmlEscape(pt.slug)}" data-section-index="${sIndex}">
                  Remove Section
                </button>
              </div>
            </div>
            ${section.fields
              .map((field, fIndex) => {
                const optionsValue = Array.isArray(field.options) ? field.options.join(", ") : "";
                return `
                <div class="field-chip">
                  <div class="field-chip-head">
                    <h5>Field ${fIndex + 1}</h5>
                    <button class="outline-btn" type="button" data-action="remove-field" data-slug="${htmlEscape(pt.slug)}" data-section-index="${sIndex}" data-field-index="${fIndex}">
                      Remove Field
                    </button>
                  </div>
                  <div class="grid-3">
                    <label class="field">
                      <span>Field key</span>
                      <input data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.name" type="text" value="${htmlEscape(field.name)}" />
                    </label>
                    <label class="field">
                      <span>Label shown to users</span>
                      <input data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.label" type="text" value="${htmlEscape(field.label)}" />
                    </label>
                    <label class="field">
                      <span>Field type</span>
                      <select data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.type">${fieldTypeOptions(field.type)}</select>
                    </label>
                  </div>
                  <div class="grid-3">
                    <label class="field">
                      <span>Visibility</span>
                      <select data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.visibility">${fieldVisibilityOptions(field.visibility)}</select>
                    </label>
                    <label class="field">
                      <span>Options (comma separated)</span>
                      <input data-options-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.options" type="text" value="${htmlEscape(optionsValue)}" />
                    </label>
                    <div class="checks">
                      <label><input data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.required" type="checkbox" ${field.required ? "checked" : ""} /> Required</label>
                      <label><input data-bind="profile_schemas.${pt.slug}.sections.${sIndex}.fields.${fIndex}.searchable" type="checkbox" ${field.searchable ? "checked" : ""} /> Searchable</label>
                    </div>
                  </div>
                </div>
              `;
              })
              .join("")}
            <button class="outline-btn" type="button" data-action="add-field" data-slug="${htmlEscape(pt.slug)}" data-section-index="${sIndex}">
              Add Field
            </button>
          </section>
        `,
          )
          .join("")}
      </article>
      `;
    })
    .join("");
}

function renderRisks() {
  const risks = [];
  const noneApproval = configState.participant_types.every((pt) => !configState.onboarding[pt.slug]?.requires_approval);
  if (noneApproval) {
    risks.push("All roles are auto-approved. Consider requiring approval for at least one listing role.");
  }
  if (!configState.communication.conversation_rules.length) {
    risks.push("No communication rules are configured. Users will not be able to contact each other.");
  }
  if (!configState.discovery.searchable_types.length) {
    risks.push("No searchable roles configured. Discovery may return no results.");
  }
  if (
    configState.discovery.access.anonymous_search_enabled &&
    configState.discovery.access.anonymous_filter_mode === "all"
  ) {
    risks.push("Anonymous filters are set to 'all'. This can expose sensitive signals through filter behavior.");
  }
  if (
    configState.discovery.ai.profile_retrieval_mode === "rag_strict" &&
    !configState.discovery.ai.vector_search_enabled
  ) {
    risks.push("RAG strict is enabled while vector search is disabled. Discovery requests may fail.");
  }
  if (risks.length === 0) {
    dom.riskList.innerHTML = "<p>No high-risk issues detected. Configuration looks launch-ready for MVP.</p>";
    return;
  }
  dom.riskList.innerHTML = risks.map((risk) => `<p>Potential risk: ${htmlEscape(risk)}</p>`).join("");
}

function renderAll() {
  dom.sourcePath.textContent = sourcePath || "runtime config";
  renderStepNav();
  renderStepPanels();
  renderPresetList();
  renderBasics();
  renderParticipants();
  renderOnboarding();
  renderCommunication();
  renderDiscovery();
  renderSchemas();
  renderRisks();
  renderGlossaryList();
}

function mapFriendlyErrors(errors) {
  const mapped = mapValidationErrors(errors);
  if (!mapped.length) {
    dom.friendlyErrors.classList.add("hidden");
    dom.friendlyErrors.innerHTML = "";
    return;
  }
  dom.friendlyErrors.classList.remove("hidden");
  dom.friendlyErrors.innerHTML = `<strong>Validation needs attention:</strong>
    <ul>
      ${mapped
        .map(
          (item, idx) => `<li>${htmlEscape(item.message)}
            <button type="button" class="ghost-btn" data-action="jump-error-step" data-step="${item.stepIndex}" data-error-index="${idx}">Go to step ${item.stepIndex + 1}</button>
          </li>`,
        )
        .join("")}
    </ul>`;
}

function renderGlossaryList() {
  const q = String(dom.glossarySearchInput.value || "").trim().toLowerCase();
  const all = [...GLOSSARY_TERMS, ...listHelpEntries().map((x) => ({ term: x.label, definition: x.description }))];
  const uniq = [];
  const seen = new Set();
  for (const item of all) {
    const key = `${item.term.toLowerCase()}::${item.definition.toLowerCase()}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniq.push(item);
    }
  }
  const filtered = q ? uniq.filter((item) => item.term.toLowerCase().includes(q) || item.definition.toLowerCase().includes(q)) : uniq;
  dom.glossaryList.innerHTML = filtered
    .map(
      (item) => `
      <article class="glossary-item">
        <strong>${htmlEscape(item.term)}</strong>
        <p>${htmlEscape(item.definition)}</p>
      </article>
    `,
    )
    .join("");
}

function showHelpPopover(path, anchorEl) {
  const help = getFieldHelp(path);
  dom.helpPopover.innerHTML = `
    <h4>${htmlEscape(help.label)}</h4>
    <p><strong>What this controls:</strong> ${htmlEscape(help.description)}</p>
    <p><strong>Why it matters:</strong> ${htmlEscape(help.whyItMatters)}</p>
    <p><strong>Example:</strong> ${htmlEscape(help.example)}</p>
    <p><strong>Recommended default:</strong> ${htmlEscape(help.recommendedDefault)}</p>
    <p><strong>Risk level:</strong> ${htmlEscape(help.riskLevel)}</p>
  `;
  const rect = anchorEl.getBoundingClientRect();
  dom.helpPopover.style.top = `${Math.max(8, rect.bottom + window.scrollY + 8)}px`;
  dom.helpPopover.style.left = `${Math.max(8, rect.left + window.scrollX - 12)}px`;
  dom.helpPopover.classList.remove("hidden");
}

function hideHelpPopover() {
  dom.helpPopover.classList.add("hidden");
}

async function apiJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw body;
  }
  return body;
}

async function loadTemplateConfig() {
  const response = await fetch("/api/setup/config-template");
  const body = await response.json();
  configState = normalizeConfig(body.config || fallbackConfig());
  sourcePath = body.source_path || "";
  lastValidatedConfig = clone(configState);
  dom.jsonEditor.value = JSON.stringify(configState, null, 2);
  renderAll();
  setStatus("ok", "Loaded current setup configuration.");
}

async function loadPresets() {
  const response = await fetch("/api/setup/presets");
  const body = await response.json();
  presets = Array.isArray(body.presets) ? body.presets : [];
  renderPresetList();
}

function applyQuickAnswers() {
  const readiness = dom.quickReadiness.value;
  const launchStyle = dom.quickLaunchStyle.value;
  for (const pt of configState.participant_types) {
    const roleOnboarding = configState.onboarding[pt.slug];
    if (readiness === "review-heavy") {
      roleOnboarding.requires_approval = true;
      roleOnboarding.approval_type = "manual";
      roleOnboarding.profile_completeness_threshold = Math.max(90, roleOnboarding.profile_completeness_threshold);
    }
    if (readiness === "lean" && pt.role === "demand") {
      roleOnboarding.requires_approval = false;
      roleOnboarding.approval_type = "auto";
    }
    if (launchStyle === "curated" && pt.role === "supply") {
      roleOnboarding.requires_approval = true;
      roleOnboarding.approval_type = "manual";
      roleOnboarding.document_upload_required = true;
    }
    if (launchStyle === "fast" && pt.role === "demand") {
      roleOnboarding.requires_approval = false;
      roleOnboarding.approval_type = "auto";
    }
  }
}

async function validateCurrentConfig({ showSuccess = true } = {}) {
  try {
    const data = await apiJson("/api/setup/validate", { config: configState });
    configState = normalizeConfig(data.config);
    lastValidatedConfig = clone(configState);
    mapFriendlyErrors([]);
    renderAll();
    if (showSuccess) {
      setStatus("ok", "Validation successful. Your setup is consistent.");
    }
    return configState;
  } catch (err) {
    const detail = err?.detail || {};
    const errs = Array.isArray(detail.errors) ? detail.errors : [];
    mapFriendlyErrors(errs);
    setStatus("error", detail.message || "Validation failed. Resolve highlighted issues.");
    return null;
  }
}

async function renderYamlPreview() {
  try {
    const data = await apiJson("/api/setup/render-yaml", { config: configState });
    dom.yamlPreview.textContent = data.yaml || "";
    setStatus("ok", "YAML preview updated.");
  } catch (err) {
    setStatus("error", err?.detail?.message || err?.detail || "Failed to render YAML.");
  }
}

async function saveConfig() {
  const valid = await validateCurrentConfig({ showSuccess: false });
  if (!valid) {
    return;
  }
  try {
    const data = await apiJson("/api/setup/save", {
      config: valid,
      output_path: dom.outputPathInput.value.trim(),
      apply_runtime: dom.applyRuntimeInput.checked,
    });
    setStatus("ok", `Saved to ${data.path}.`);
  } catch (err) {
    setStatus("error", err?.detail || "Failed to save config.");
  }
}

async function checkGeneratedSync() {
  const valid = await validateCurrentConfig({ showSuccess: false });
  if (!valid) {
    return;
  }
  try {
    const data = await apiJson("/api/setup/generate/check", {
      config: valid,
      mode: dom.compileModeInput.value,
      overwrite_policy: "managed",
    });
    dom.generateReport.textContent = JSON.stringify(data, null, 2);
    setStatus(data.in_sync ? "ok" : "warn", data.in_sync ? "Generated artifacts are in sync." : "Generated artifacts are out of sync. Run Generate Project.");
  } catch (err) {
    setStatus("error", err?.detail?.message || err?.detail || "Failed to check generated sync.");
  }
}

async function generateProject() {
  const valid = await validateCurrentConfig({ showSuccess: false });
  if (!valid) {
    return;
  }
  try {
    const data = await apiJson("/api/setup/generate", {
      config: valid,
      mode: dom.compileModeInput.value,
      export_enabled: dom.exportEnabledInput.checked,
      export_dir: dom.exportDirInput.value.trim() || "exports",
      overwrite_policy: "managed",
    });
    dom.generateReport.textContent = JSON.stringify(data, null, 2);
    if (data.export_path) {
      setStatus("ok", `Generation complete. Export created at ${data.export_path}.`);
    } else {
      setStatus("ok", "Generation complete.");
    }
  } catch (err) {
    setStatus("error", err?.detail?.message || err?.detail || "Failed to generate project.");
  }
}

function setMode(nextAdvanced) {
  advancedMode = nextAdvanced;
  dom.guidedModeBtn.classList.toggle("active", !advancedMode);
  dom.advancedModeBtn.classList.toggle("active", advancedMode);
  dom.guidedModeBtn.setAttribute("aria-selected", String(!advancedMode));
  dom.advancedModeBtn.setAttribute("aria-selected", String(advancedMode));
  dom.advancedPanel.classList.toggle("hidden", !advancedMode);
  if (advancedMode) {
    dom.jsonEditor.value = JSON.stringify(configState, null, 2);
    validateJsonDraftNow();
  }
}

function setJsonStatus(kind, message) {
  dom.jsonStatus.className = `json-status ${kind || ""}`.trim();
  dom.jsonStatus.textContent = message;
}

async function validateJsonDraftNow() {
  const raw = dom.jsonEditor.value.trim();
  if (!raw) {
    jsonDraftValid = false;
    jsonDraftConfig = null;
    dom.applyJsonBtn.disabled = true;
    setJsonStatus("warn", "JSON editor is empty.");
    dom.jsonDiff.innerHTML = "No JSON impact preview yet.";
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    jsonDraftValid = false;
    jsonDraftConfig = null;
    dom.applyJsonBtn.disabled = true;
    setJsonStatus("error", `JSON syntax error: ${error.message}`);
    dom.jsonDiff.innerHTML = "<p>Fix syntax errors to preview impact.</p>";
    return;
  }
  const normalized = normalizeConfig(parsed);
  try {
    const data = await apiJson("/api/setup/validate", { config: normalized });
    jsonDraftConfig = normalizeConfig(data.config);
    jsonDraftValid = true;
    const baseline = lastValidatedConfig || configState;
    latestJsonDiff = buildConfigDiff(baseline, jsonDraftConfig);
    dom.jsonDiff.innerHTML = renderDiffHtml(latestJsonDiff);
    if (latestJsonDiff.destructiveCount > 0) {
      dom.jsonDiff.innerHTML += `<p class="destructive">Warning: ${latestJsonDiff.destructiveCount} potentially breaking changes detected.</p>`;
      setJsonStatus("warn", "JSON is valid, but includes potentially breaking changes.");
    } else {
      setJsonStatus("ok", "JSON is valid and safe to apply.");
    }
    dom.applyJsonBtn.disabled = false;
  } catch (err) {
    jsonDraftValid = false;
    jsonDraftConfig = null;
    dom.applyJsonBtn.disabled = true;
    const detail = err?.detail || {};
    const mapped = mapValidationErrors(Array.isArray(detail.errors) ? detail.errors : []);
    const bullets = mapped.map((m) => `- ${m.message}`).join("\n");
    dom.jsonDiff.innerHTML = `<pre>${htmlEscape(bullets || "JSON failed backend validation.")}</pre>`;
    setJsonStatus("error", detail.message || "JSON failed backend validation.");
  }
}

function debouncedValidateJson() {
  if (jsonValidationTimer) {
    window.clearTimeout(jsonValidationTimer);
  }
  jsonValidationTimer = window.setTimeout(() => {
    validateJsonDraftNow();
  }, 350);
}

function applyJsonToGuided() {
  if (!jsonDraftValid || !jsonDraftConfig) {
    return;
  }
  if (latestJsonDiff?.destructiveCount > 0) {
    const ok = window.confirm(
      "This JSON includes potentially breaking changes (like role slug or schema structural updates). Apply anyway?",
    );
    if (!ok) {
      return;
    }
  }
  configState = normalizeConfig(jsonDraftConfig);
  lastValidatedConfig = clone(configState);
  renderAll();
  setStatus("ok", "Advanced JSON changes applied to guided setup.");
}

function addParticipant() {
  const idx = configState.participant_types.length + 1;
  const slug = `role_${idx}`;
  configState.participant_types.push(createParticipant(slug, "supply"));
  configState.onboarding[slug] = clone(configState.onboarding[currentSlugs(configState)[0]] || {});
  configState.profile_schemas[slug] = { sections: [defaultSection("Main", "primary_field")] };
  renderAll();
  setStatus("warn", `Added role ${slug}.`);
}

function removeParticipant(index) {
  if (configState.participant_types.length <= 2) {
    setStatus("warn", "At least two roles are required.");
    return;
  }
  const removed = configState.participant_types.splice(index, 1)[0];
  delete configState.onboarding[removed.slug];
  delete configState.profile_schemas[removed.slug];
  configState.discovery.searchable_types = configState.discovery.searchable_types.filter((slug) => slug !== removed.slug);
  configState.communication.conversation_rules = configState.communication.conversation_rules.filter(
    (rule) => rule.initiator !== removed.slug && rule.receiver !== removed.slug,
  );
  renderAll();
  setStatus("warn", `Removed role ${removed.slug}.`);
}

function addRule() {
  const slugs = currentSlugs(configState);
  if (slugs.length < 2) {
    setStatus("warn", "Add more roles before creating communication rules.");
    return;
  }
  configState.communication.conversation_rules.push({
    initiator: slugs[0],
    receiver: slugs[1],
    requires_approval: true,
  });
  renderAll();
}

function addSection(slug) {
  const schema = configState.profile_schemas[slug];
  schema.sections.push(defaultSection("New Section", "new_field"));
  renderAll();
}

function removeSection(slug, sectionIndex) {
  const sections = configState.profile_schemas[slug].sections;
  sections.splice(sectionIndex, 1);
  if (!sections.length) {
    sections.push(defaultSection("Main", "primary_field"));
  }
  renderAll();
}

function addField(slug, sectionIndex) {
  configState.profile_schemas[slug].sections[sectionIndex].fields.push(defaultField());
  renderAll();
}

function removeField(slug, sectionIndex, fieldIndex) {
  const fields = configState.profile_schemas[slug].sections[sectionIndex].fields;
  fields.splice(fieldIndex, 1);
  if (!fields.length) {
    fields.push(defaultField());
  }
  renderAll();
}

function bindEvents() {
  dom.prevStepBtn.addEventListener("click", () => setActiveStep(activeStep - 1));
  dom.nextStepBtn.addEventListener("click", () => {
    if (activeStep < STEPS.length - 1) {
      setActiveStep(activeStep + 1);
    }
  });

  dom.guidedModeBtn.addEventListener("click", () => setMode(false));
  dom.advancedModeBtn.addEventListener("click", () => setMode(true));
  dom.openGlossaryBtn.addEventListener("click", () => dom.glossaryDrawer.classList.remove("hidden"));
  dom.closeGlossaryBtn.addEventListener("click", () => dom.glossaryDrawer.classList.add("hidden"));
  dom.glossarySearchInput.addEventListener("input", renderGlossaryList);

  dom.quickReadiness.addEventListener("change", () => {
    applyQuickAnswers();
    renderAll();
  });
  dom.quickLaunchStyle.addEventListener("change", () => {
    applyQuickAnswers();
    renderAll();
  });

  dom.loadConfigBtn.addEventListener("click", loadTemplateConfig);
  dom.validateBtn.addEventListener("click", () => validateCurrentConfig());
  dom.renderYamlBtn.addEventListener("click", renderYamlPreview);
  dom.saveBtn.addEventListener("click", saveConfig);
  dom.checkGeneratedBtn.addEventListener("click", checkGeneratedSync);
  dom.generateBtn.addEventListener("click", generateProject);
  dom.addParticipantBtn.addEventListener("click", addParticipant);
  dom.addRuleBtn.addEventListener("click", addRule);

  dom.formatJsonBtn.addEventListener("click", () => {
    try {
      const parsed = JSON.parse(dom.jsonEditor.value);
      dom.jsonEditor.value = JSON.stringify(parsed, null, 2);
      debouncedValidateJson();
    } catch {
      setJsonStatus("error", "Cannot format invalid JSON.");
    }
  });
  dom.applyJsonBtn.addEventListener("click", applyJsonToGuided);
  dom.jsonEditor.addEventListener("input", debouncedValidateJson);

  dom.workspaceInputHandler = (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (target.dataset.searchableType !== undefined) {
      const checks = Array.from(dom.searchableTypes.querySelectorAll("input[data-searchable-type]"));
      configState.discovery.searchable_types = checks.filter((c) => c.checked).map((c) => c.dataset.searchableType);
      renderStepNav();
      return;
    }
    if (target === dom.filterFieldsInput) {
      configState.discovery.filter_fields = dom.filterFieldsInput.value.split(",").map((x) => x.trim()).filter(Boolean);
      renderStepNav();
      return;
    }
    if (target === dom.anonymousVisibility) {
      configState.discovery.result_visibility.anonymous = dom.anonymousVisibility.value;
      renderStepNav();
      return;
    }
    if (target === dom.authenticatedVisibility) {
      configState.discovery.result_visibility.authenticated = dom.authenticatedVisibility.value;
      renderStepNav();
      return;
    }
    if (target === dom.anonymousSearchEnabled) {
      configState.discovery.access.anonymous_search_enabled = dom.anonymousSearchEnabled.checked;
      renderStepNav();
      return;
    }
    if (target === dom.anonymousFilterMode) {
      configState.discovery.access.anonymous_filter_mode = dom.anonymousFilterMode.value;
      renderStepNav();
      return;
    }
    if (target === dom.vectorSearchEnabled) {
      configState.discovery.ai.vector_search_enabled = dom.vectorSearchEnabled.checked;
      renderStepNav();
      return;
    }
    if (target === dom.ragQueryEnabled) {
      configState.discovery.ai.rag_query_enabled = dom.ragQueryEnabled.checked;
      renderStepNav();
      return;
    }
    if (target === dom.followUpSuggestions) {
      configState.discovery.ai.follow_up_suggestions = dom.followUpSuggestions.checked;
      renderStepNav();
      return;
    }
    if (target === dom.profileRetrievalMode) {
      configState.discovery.ai.profile_retrieval_mode = dom.profileRetrievalMode.value;
      renderStepNav();
      return;
    }
    if (target === dom.ragFailureBehavior) {
      configState.discovery.ai.rag_failure_behavior = dom.ragFailureBehavior.value;
      renderStepNav();
      return;
    }
    if (target === dom.profileSimilarityThreshold) {
      configState.discovery.ai.profile_similarity_threshold = Number(dom.profileSimilarityThreshold.value || 0);
      renderStepNav();
      return;
    }
    if (target === dom.maxVectorCandidates) {
      configState.discovery.ai.max_vector_candidates = Number(dom.maxVectorCandidates.value || 1);
      renderStepNav();
      return;
    }
    const bind = target.dataset.bind;
    if (bind) {
      const value =
        target instanceof HTMLInputElement && target.type === "checkbox"
          ? target.checked
          : target instanceof HTMLInputElement && target.type === "number"
            ? Number(target.value || 0)
            : target.value;
      setAtPath(configState, bind, value);
      if (target.dataset.slugInput === "true") {
        const match = bind.match(/^participant_types\.(\d+)\.slug$/);
        if (match) {
          const index = Number(match[1]);
          const remap = updateSlugReferences(configState, index, target.value);
          setStatus("warn", `Role slug updated: ${remap.oldSlug} -> ${remap.newSlug}`);
        }
        renderAll();
      } else {
        renderStepNav();
      }
      return;
    }
    const optionsBind = target.dataset.optionsBind;
    if (optionsBind) {
      const values = target.value
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      setAtPath(configState, optionsBind, values.length ? values : null);
      renderStepNav();
      return;
    }
  };

  document.addEventListener("change", dom.workspaceInputHandler);
  document.addEventListener("input", (event) => {
    const target = event.target;
    if (target === dom.marketplaceName) {
      configState.marketplace.name = dom.marketplaceName.value;
    } else if (target === dom.marketplaceDescription) {
      configState.marketplace.description = dom.marketplaceDescription.value;
    } else if (target === dom.marketplaceIndustry) {
      configState.marketplace.industry = dom.marketplaceIndustry.value;
    }
    renderStepNav();
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const help = target.closest("[data-help-path]");
    if (help) {
      event.preventDefault();
      showHelpPopover(help.dataset.helpPath, help);
      return;
    }
    if (!target.closest("#helpPopover")) {
      hideHelpPopover();
    }

    const stepBtn = target.closest("[data-step-nav]");
    if (stepBtn) {
      setActiveStep(Number(stepBtn.dataset.stepNav));
      return;
    }

    const actionBtn = target.closest("[data-action]");
    if (!actionBtn) {
      return;
    }
    const action = actionBtn.dataset.action;
    if (action === "apply-preset") {
      const preset = presets.find((p) => p.id === actionBtn.dataset.presetId);
      if (preset) {
        configState = normalizeConfig(preset.config);
        applyQuickAnswers();
        setActiveStep(1);
        setStatus("ok", `${preset.title} template applied.`);
      }
      return;
    }
    if (action === "remove-participant") {
      removeParticipant(Number(actionBtn.dataset.index));
      return;
    }
    if (action === "remove-rule") {
      configState.communication.conversation_rules.splice(Number(actionBtn.dataset.index), 1);
      renderAll();
      return;
    }
    if (action === "add-section") {
      addSection(actionBtn.dataset.slug);
      return;
    }
    if (action === "remove-section") {
      removeSection(actionBtn.dataset.slug, Number(actionBtn.dataset.sectionIndex));
      return;
    }
    if (action === "add-field") {
      addField(actionBtn.dataset.slug, Number(actionBtn.dataset.sectionIndex));
      return;
    }
    if (action === "remove-field") {
      removeField(actionBtn.dataset.slug, Number(actionBtn.dataset.sectionIndex), Number(actionBtn.dataset.fieldIndex));
      return;
    }
    if (action === "jump-error-step") {
      setActiveStep(Number(actionBtn.dataset.step));
    }
  });
}

async function bootstrap() {
  maybeReduceMotion();
  bindEvents();
  setStatus("warn", "Loading onboarding setup...");
  try {
    await Promise.all([loadTemplateConfig(), loadPresets()]);
    setStatus("ok", "Setup ready. Start at Step 1 and apply a template.");
  } catch (error) {
    setStatus("error", "Failed to load setup data.");
    dom.generateReport.textContent = JSON.stringify(error, null, 2);
  }
}

bootstrap();
