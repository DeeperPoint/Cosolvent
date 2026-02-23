export const RESERVED_SLUGS = new Set([
  "admin", "auth", "search", "files", "notifications", "setup",
  "docs", "openapi", "roles", "ws",
]);

export const DEFAULT_PERMISSIONS = Object.freeze({
  can_list: false,
  can_search: false,
  can_initiate_conversation: false,
  can_receive_conversation: false,
  can_share_private_assets: false,
  requires_onboarding: true,
  requires_approval: false,
  visible_in_search: false,
});

export const DEFAULT_ONBOARDING = Object.freeze({
  requires_approval: true,
  approval_type: "manual",
  document_upload_required: false,
  ai_extraction_enabled: false,
  ai_profile_generation: false,
  welcome_email_on_approval: true,
  profile_completeness_threshold: 100,
});

export const DEFAULT_DISCOVERY = Object.freeze({
  searchable_types: [],
  filter_fields: [],
  result_visibility: {
    anonymous: "public",
    authenticated: "protected",
  },
  access: {
    anonymous_search_enabled: false,
    anonymous_filter_mode: "public_only",
  },
  ai: {
    vector_search_enabled: true,
    rag_query_enabled: true,
    follow_up_suggestions: true,
    profile_retrieval_mode: "hybrid",
    rag_failure_behavior: "service_unavailable",
    profile_similarity_threshold: 0.25,
    max_vector_candidates: 500,
  },
});

export function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function titleize(raw) {
  return String(raw || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

export function sanitizeSlug(value) {
  let slug = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_\- ]/g, "")
    .replace(/\s+/g, "_");
  if (RESERVED_SLUGS.has(slug)) slug = `${slug}_role`;
  return slug;
}

export function createParticipant(slug, role = "supply") {
  return {
    name: titleize(slug),
    slug,
    role,
    permissions: clone(DEFAULT_PERMISSIONS),
  };
}

export function defaultField() {
  return {
    name: "new_field",
    label: "New Field",
    type: "text",
    required: false,
    options: null,
    visibility: "public",
    searchable: false,
  };
}

export function defaultSection(name = "Main", fieldName = "primary_field") {
  return {
    name,
    fields: [
      {
        name: fieldName,
        label: titleize(fieldName),
        type: "text",
        required: true,
        options: null,
        visibility: "public",
        searchable: true,
      },
    ],
  };
}

export function fallbackConfig() {
  return {
    marketplace: {
      name: "New Marketplace",
      description: "",
      industry: "",
    },
    participant_types: [
      {
        name: "Provider",
        slug: "provider",
        role: "supply",
        permissions: {
          ...clone(DEFAULT_PERMISSIONS),
          can_list: true,
          can_receive_conversation: true,
          requires_onboarding: true,
          requires_approval: true,
          visible_in_search: true,
        },
      },
      {
        name: "Client",
        slug: "client",
        role: "demand",
        permissions: {
          ...clone(DEFAULT_PERMISSIONS),
          can_search: true,
          can_initiate_conversation: true,
          requires_onboarding: true,
        },
      },
    ],
    profile_schemas: {
      provider: { sections: [defaultSection("Provider Profile", "company_name")] },
      client: { sections: [defaultSection("Client Profile", "organization_name")] },
    },
    onboarding: {
      provider: clone(DEFAULT_ONBOARDING),
      client: clone(DEFAULT_ONBOARDING),
    },
    communication: {
      conversation_rules: [{ initiator: "client", receiver: "provider", requires_approval: true }],
    },
    discovery: {
      ...clone(DEFAULT_DISCOVERY),
      searchable_types: ["provider"],
    },
  };
}

export function currentSlugs(cfg) {
  return (cfg?.participant_types || []).map((pt) => pt.slug);
}

export function getAtPath(obj, path) {
  return String(path || "")
    .split(".")
    .reduce((acc, seg) => (acc == null ? undefined : acc[seg]), obj);
}

export function setAtPath(obj, path, value) {
  const parts = String(path || "").split(".");
  let ptr = obj;
  for (let i = 0; i < parts.length - 1; i += 1) {
    const key = parts[i];
    const nextKey = parts[i + 1];
    if (ptr[key] == null) {
      ptr[key] = /^\d+$/.test(nextKey) ? [] : {};
    }
    ptr = ptr[key];
  }
  ptr[parts[parts.length - 1]] = value;
}

function remapKeyedObject(obj, oldKey, newKey, fallbackFactory) {
  if (oldKey === newKey) {
    return obj;
  }
  const next = {};
  Object.keys(obj).forEach((key) => {
    if (key === oldKey) {
      next[newKey] = obj[key];
    } else if (key !== newKey) {
      next[key] = obj[key];
    }
  });
  if (!next[newKey]) {
    next[newKey] = fallbackFactory();
  }
  return next;
}

export function updateSlugReferences(cfg, index, newRawSlug) {
  const oldSlug = cfg.participant_types[index].slug;
  let newSlug = sanitizeSlug(newRawSlug);
  if (!newSlug) {
    newSlug = oldSlug;
  }
  const otherSlugs = cfg.participant_types.filter((_, idx) => idx !== index).map((pt) => pt.slug);
  let candidate = newSlug;
  let i = 1;
  while (otherSlugs.includes(candidate)) {
    i += 1;
    candidate = `${newSlug}_${i}`;
  }
  newSlug = candidate;
  cfg.participant_types[index].slug = newSlug;
  cfg.onboarding = remapKeyedObject(cfg.onboarding, oldSlug, newSlug, () => clone(DEFAULT_ONBOARDING));
  cfg.profile_schemas = remapKeyedObject(cfg.profile_schemas, oldSlug, newSlug, () => ({ sections: [] }));
  cfg.discovery.searchable_types = cfg.discovery.searchable_types.map((slug) => (slug === oldSlug ? newSlug : slug));
  cfg.communication.conversation_rules = cfg.communication.conversation_rules.map((rule) => ({
    ...rule,
    initiator: rule.initiator === oldSlug ? newSlug : rule.initiator,
    receiver: rule.receiver === oldSlug ? newSlug : rule.receiver,
  }));
  return { oldSlug, newSlug };
}

export function normalizeConfig(raw) {
  const cfg = clone(raw || fallbackConfig());
  cfg.marketplace = cfg.marketplace && typeof cfg.marketplace === "object" ? cfg.marketplace : {};
  cfg.marketplace.name = String(cfg.marketplace.name || "New Marketplace");
  cfg.marketplace.description = String(cfg.marketplace.description || "");
  cfg.marketplace.industry = String(cfg.marketplace.industry || "");

  cfg.participant_types = Array.isArray(cfg.participant_types) ? cfg.participant_types : [];
  cfg.participant_types = cfg.participant_types.map((pt, idx) => ({
    name: String(pt?.name || titleize(pt?.slug || `type_${idx + 1}`)),
    slug: sanitizeSlug(pt?.slug || `type_${idx + 1}`) || `type_${idx + 1}`,
    role: ["supply", "demand", "facilitator"].includes(pt?.role) ? pt.role : "supply",
    permissions: { ...clone(DEFAULT_PERMISSIONS), ...(pt?.permissions || {}) },
  }));
  if (cfg.participant_types.length < 2) {
    cfg.participant_types = fallbackConfig().participant_types;
  }

  cfg.profile_schemas = cfg.profile_schemas && typeof cfg.profile_schemas === "object" ? cfg.profile_schemas : {};
  cfg.onboarding = cfg.onboarding && typeof cfg.onboarding === "object" ? cfg.onboarding : {};
  cfg.communication = cfg.communication && typeof cfg.communication === "object" ? cfg.communication : {};
  cfg.communication.conversation_rules = Array.isArray(cfg.communication.conversation_rules)
    ? cfg.communication.conversation_rules
    : [];
  cfg.discovery = { ...clone(DEFAULT_DISCOVERY), ...(cfg.discovery || {}) };
  cfg.discovery.result_visibility = { ...clone(DEFAULT_DISCOVERY.result_visibility), ...(cfg.discovery.result_visibility || {}) };
  cfg.discovery.access = { ...clone(DEFAULT_DISCOVERY.access), ...(cfg.discovery.access || {}) };
  cfg.discovery.ai = { ...clone(DEFAULT_DISCOVERY.ai), ...(cfg.discovery.ai || {}) };
  cfg.discovery.filter_fields = Array.isArray(cfg.discovery.filter_fields) ? cfg.discovery.filter_fields : [];
  cfg.discovery.searchable_types = Array.isArray(cfg.discovery.searchable_types) ? cfg.discovery.searchable_types : [];
  cfg.discovery.access.anonymous_search_enabled = Boolean(cfg.discovery.access.anonymous_search_enabled);
  cfg.discovery.access.anonymous_filter_mode = ["public_only", "none", "all"].includes(cfg.discovery.access.anonymous_filter_mode)
    ? cfg.discovery.access.anonymous_filter_mode
    : "public_only";
  cfg.discovery.ai.profile_retrieval_mode = ["hybrid", "rag_strict"].includes(cfg.discovery.ai.profile_retrieval_mode)
    ? cfg.discovery.ai.profile_retrieval_mode
    : "hybrid";
  cfg.discovery.ai.rag_failure_behavior = ["service_unavailable", "empty"].includes(cfg.discovery.ai.rag_failure_behavior)
    ? cfg.discovery.ai.rag_failure_behavior
    : "service_unavailable";
  cfg.discovery.ai.profile_similarity_threshold = Number.isFinite(Number(cfg.discovery.ai.profile_similarity_threshold))
    ? Number(cfg.discovery.ai.profile_similarity_threshold)
    : 0.25;
  cfg.discovery.ai.max_vector_candidates = Number.isFinite(Number(cfg.discovery.ai.max_vector_candidates))
    ? Number(cfg.discovery.ai.max_vector_candidates)
    : 500;
  cfg.discovery.ai.profile_similarity_threshold = Math.min(
    1,
    Math.max(0, cfg.discovery.ai.profile_similarity_threshold),
  );
  cfg.discovery.ai.max_vector_candidates = Math.max(
    1,
    Math.round(cfg.discovery.ai.max_vector_candidates),
  );

  const validSlugs = new Set();
  const seen = new Set();
  cfg.participant_types.forEach((pt, idx) => {
    let slug = pt.slug || `type_${idx + 1}`;
    let base = slug;
    let i = 1;
    while (seen.has(slug)) {
      i += 1;
      slug = `${base}_${i}`;
    }
    seen.add(slug);
    pt.slug = slug;
    validSlugs.add(slug);
  });

  const onboarding = {};
  const schemas = {};
  cfg.participant_types.forEach((pt) => {
    onboarding[pt.slug] = { ...clone(DEFAULT_ONBOARDING), ...(cfg.onboarding[pt.slug] || {}) };
    const schema = cfg.profile_schemas[pt.slug] || { sections: [defaultSection("Main", "primary_field")] };
    schema.sections = Array.isArray(schema.sections) ? schema.sections : [];
    schema.sections = schema.sections.length
      ? schema.sections.map((section) => ({
          name: String(section?.name || "Main"),
          fields: Array.isArray(section?.fields) && section.fields.length
            ? section.fields.map((field) => ({
                ...defaultField(),
                ...field,
                name: String(field?.name || "new_field"),
                label: String(field?.label || titleize(field?.name || "new_field")),
                type: field?.type || "text",
                visibility: field?.visibility || "public",
              }))
            : [defaultField()],
        }))
      : [defaultSection("Main", "primary_field")];
    schemas[pt.slug] = schema;
  });
  cfg.onboarding = onboarding;
  cfg.profile_schemas = schemas;
  cfg.discovery.searchable_types = cfg.discovery.searchable_types.filter((slug) => validSlugs.has(slug));
  cfg.communication.conversation_rules = cfg.communication.conversation_rules
    .map((rule) => ({
      initiator: validSlugs.has(rule?.initiator) ? rule.initiator : cfg.participant_types[0].slug,
      receiver: validSlugs.has(rule?.receiver) ? rule.receiver : cfg.participant_types[0].slug,
      requires_approval: Boolean(rule?.requires_approval),
    }))
    .filter((rule) => rule.initiator && rule.receiver);
  if (cfg.communication.conversation_rules.length === 0 && cfg.participant_types.length > 1) {
    cfg.communication.conversation_rules.push({
      initiator: cfg.participant_types[1].slug,
      receiver: cfg.participant_types[0].slug,
      requires_approval: true,
    });
  }
  return cfg;
}

export function htmlEscape(raw) {
  return String(raw || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
