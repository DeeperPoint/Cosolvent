const HELP_ENTRIES = [
  {
    pattern: "marketplace.name",
    label: "Marketplace Name",
    description: "The public brand name of your marketplace.",
    whyItMatters: "Used in generated project artifacts and admin experience.",
    example: "AgriExchange",
    recommendedDefault: "Use a short brand-like name.",
    riskLevel: "low",
  },
  {
    pattern: "marketplace.description",
    label: "Marketplace Description",
    description: "A one-line summary of what your platform does.",
    whyItMatters: "Guides admins and operators during onboarding and setup.",
    example: "Connecting verified producers with wholesale buyers.",
    recommendedDefault: "One sentence, plain language.",
    riskLevel: "low",
  },
  {
    pattern: "participant_types.*.name",
    label: "Role Name",
    description: "Human-facing role name shown to users.",
    whyItMatters: "Appears in onboarding and role-aware aliases.",
    example: "Producer",
    recommendedDefault: "Singular noun, title case.",
    riskLevel: "medium",
  },
  {
    pattern: "participant_types.*.slug",
    label: "Role Slug",
    description: "Internal role identifier used in URLs and generated aliases.",
    whyItMatters: "Changing slug can affect generated endpoints and references.",
    example: "producer",
    recommendedDefault: "Lowercase letters with underscores.",
    riskLevel: "high",
  },
  {
    pattern: "participant_types.*.permissions.can_search",
    label: "Can Search",
    description: "Allows this role to run discovery searches.",
    whyItMatters: "At least one role must be able to search.",
    example: "Buyer role can search suppliers.",
    recommendedDefault: "Enable for demand-side roles.",
    riskLevel: "medium",
  },
  {
    pattern: "participant_types.*.permissions.visible_in_search",
    label: "Visible in Search",
    description: "Makes this role discoverable in search results.",
    whyItMatters: "At least one role must be visible for discovery to work.",
    example: "Producer role visible in search.",
    recommendedDefault: "Enable for listing/provider roles.",
    riskLevel: "medium",
  },
  {
    pattern: "onboarding.*.requires_approval",
    label: "Requires Approval",
    description: "New profiles for this role require admin review.",
    whyItMatters: "Improves trust, but adds operational workload.",
    example: "Manual review for sellers; auto for buyers.",
    recommendedDefault: "Enable for supply-side roles.",
    riskLevel: "medium",
  },
  {
    pattern: "onboarding.*.profile_completeness_threshold",
    label: "Completeness Threshold",
    description: "Minimum profile completion percentage before submission.",
    whyItMatters: "Higher thresholds improve profile quality.",
    example: "80 for suppliers, 100 for buyers.",
    recommendedDefault: "80 to 100",
    riskLevel: "low",
  },
  {
    pattern: "communication.conversation_rules.*",
    label: "Conversation Rule",
    description: "Defines who can initiate conversations with whom.",
    whyItMatters: "Controls platform trust and message volume.",
    example: "Buyers can request chat with producers.",
    recommendedDefault: "Start with one demand -> supply rule.",
    riskLevel: "medium",
  },
  {
    pattern: "discovery.searchable_types",
    label: "Searchable Roles",
    description: "Roles included in discovery search results.",
    whyItMatters: "Determines which profiles can be found.",
    example: "Only providers/search targets are searchable.",
    recommendedDefault: "Include primary listing role.",
    riskLevel: "medium",
  },
  {
    pattern: "profile_schemas.*.sections.*.fields.*.visibility",
    label: "Field Visibility",
    description: "Who can see this field: public, protected, or private.",
    whyItMatters: "Affects privacy and conversion quality.",
    example: "Pricing terms as protected.",
    recommendedDefault: "Default to public unless sensitive.",
    riskLevel: "high",
  },
];

export const GLOSSARY_TERMS = [
  {
    term: "Participant role",
    definition: "A user type in your marketplace, like Producer or Buyer.",
  },
  {
    term: "Approval",
    definition: "Admin review step before a profile becomes active.",
  },
  {
    term: "Discovery",
    definition: "Search and filtering behavior used to find profiles.",
  },
  {
    term: "Visibility",
    definition: "Controls who can see profile information.",
  },
  {
    term: "Profile schema",
    definition: "Definition of sections and fields each role must fill.",
  },
  {
    term: "Generated aliases",
    definition: "Role-specific endpoint aliases generated from your role slugs.",
  },
];

function normalize(path) {
  return String(path || "").replace(/\.\d+\./g, ".*.").replace(/\.\d+$/g, ".*");
}

function wildcardMatch(pattern, path) {
  const source = pattern
    .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, "[^.]+");
  const re = new RegExp(`^${source}$`);
  return re.test(path);
}

export function getFieldHelp(path) {
  const normalized = normalize(path);
  const entry = HELP_ENTRIES.find((item) => wildcardMatch(item.pattern, normalized));
  if (entry) {
    return entry;
  }
  return {
    label: "Configuration Field",
    description: "Adjusts how your marketplace behaves.",
    whyItMatters: "This setting can change onboarding or runtime behavior.",
    example: "Use recommended defaults unless you have a clear policy need.",
    recommendedDefault: "Keep defaults first, tune after launch.",
    riskLevel: "medium",
  };
}

export function listHelpEntries() {
  return HELP_ENTRIES.slice();
}
