"""content_governance — governed legal content: rule packs, taxonomy, templates.

Owns the platform-wide (non-tenant) legal content that other modules pin by
version: the RTA matter taxonomy, intake question definitions, checklist
requirement definitions, deterministic check definitions, and prescribed form
templates with their field mappings.

Nothing in this module is client data. Nothing in it is lawyer-approved until a
named lawyer records the approval (``source-governance`` rules, RTA workflow
spec §13).
"""
