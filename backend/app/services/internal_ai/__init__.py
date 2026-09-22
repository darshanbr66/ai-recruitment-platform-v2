"""The internal AI ("Recruitment Intelligence") service layer — authenticated
recruiter/admin natural-language access to candidates, applications and
jobs (product brief § 1/§ 3), backed by app/services/matching/'s explainable
scoring engine. Never reachable from, or importing from, the public Sigvi
surface (app/services/sigvi_service.py) — see internal_ai_service.py's
module docstring.
"""
