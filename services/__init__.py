"""Application service layer — bridges core domain and GUI.

Services are stateless (except AppContext which holds singletons).
All global state from the old architecture is migrated here so
it can be injected rather than imported.
"""
