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
    match: "Maximum 3 participant types",
    friendly: "You have more than 3 roles. Remove one before generating.",
    stepIndex: 2,
  },
  {
    match: "is reserved and cannot be used",
    friendly: "One of your role slugs uses a reserved word (admin, search, auth…). Rename that role slug.",
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
    stepIndex: 5,
  },
  {
    match: "options required for select/multi_select",
    friendly: "A profile field of type 'select' or 'multi_select' needs at least one option value. Open the field's 'Visibility, search, options' section and add comma-separated options.",
    stepIndex: 6,
  },
  {
    match: "Discovery searchable_types references unknown",
    friendly: "One searchable role is invalid. Re-check discovery role selections.",
    stepIndex: 6,
  },
  {
    match: "Discovery searchable_type",
    friendly: "Each searchable role must also be marked visible in search.",
    stepIndex: 6,
  },
  {
    match: "Discovery filter_field",
    friendly: "A discovery filter field does not exist in any profile schema.",
    stepIndex: 6,
  },
  {
    match: "profile_similarity_threshold must be between 0 and 1",
    friendly: "Similarity threshold must stay between 0.00 and 1.00.",
    stepIndex: 6,
  },
  {
    match: "max_vector_candidates must be >= 1",
    friendly: "Max vector candidates must be at least 1.",
    stepIndex: 6,
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
    return 5;
  }
  if (path.startsWith("profile_schemas.") || path.startsWith("discovery.")) {
    return 6;
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
