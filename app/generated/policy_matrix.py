"""Generated policy matrix derived from marketplace config."""

SPEC_HASH = "096ab1bd61cf63b4c1b6209f8d9845f43e0235b00edffc18669afbe7ce089525"
PERMISSIONS_BY_ROLE = {'buyer': {'can_initiate_conversation': True,
           'can_list': False,
           'can_receive_conversation': True,
           'can_search': True,
           'can_share_private_assets': False,
           'requires_approval': False,
           'requires_onboarding': True,
           'visible_in_search': False},
 'producer': {'can_initiate_conversation': False,
              'can_list': True,
              'can_receive_conversation': True,
              'can_search': False,
              'can_share_private_assets': True,
              'requires_approval': True,
              'requires_onboarding': True,
              'visible_in_search': True}}
COMMUNICATION_RULES = [{'initiator': 'buyer', 'receiver': 'producer', 'requires_approval': True}]
DISCOVERY_FILTER_FIELDS = ['country', 'primary_crops', 'certifications']
