"""Canned sample output for demo mode.

Demo mode lets you run and show AegisMed with NO API key and at zero cost.
The answers below were written by hand for the built-in example case
(a classic, frequently missed presentation of Fabry disease) so the app
looks and behaves exactly as it will with the real AI connected.
"""

DEMO_BANNER = (
    "DEMO MODE — this is pre-written sample output, not a live AI response. "
    "Add your Fireworks API key to .env to enable the real specialist agents."
)

# Canned intake questions for demo mode (the real intake agent tailors these to
# each specific case). Must be a JSON string — aegismed/intake.py parses it.
DEMO_INTAKE = """{
  "ready": false,
  "questions": [
    {"question": "How long have the symptoms been present, and are they constant or episodic (any triggers such as exertion, heat, foods, or medications)?",
     "why": "timeline and triggers separate inherited/metabolic causes from acquired ones"},
    {"question": "Is there any family history of similar symptoms, early organ failure, or unexplained early deaths?",
     "why": "points toward or away from a genetic diagnosis"},
    {"question": "Have any prior tests, imaging, or biopsies been done, and what did they show?",
     "why": "avoids repeating work and can narrow the differential quickly"}
  ]
}"""

# The example patient case shown by the "Load example case" button in the UI.
EXAMPLE_CASE = {
    "age": "24",
    "sex": "male",
    "symptoms": (
        "Recurrent episodes of severe burning pain in both hands and feet since "
        "childhood, worse with exercise, fever, or hot weather. Reports he "
        "almost never sweats. Small dark-red spots clustered around the umbilicus "
        "and on the buttocks. Occasional abdominal pain and diarrhea after meals. "
        "Recently more tired than usual."
    ),
    "history": (
        "Episodes since about age 10, repeatedly diagnosed as 'growing pains'. "
        "Maternal uncle died of kidney failure at 45. Mother has occasional "
        "similar hand pain. No medications. Non-smoker."
    ),
    "labs": (
        "Urinalysis: proteinuria 1+. Creatinine 1.3 mg/dL (mildly elevated). "
        "CBC normal. ESR/CRP normal between episodes. ECG: mild LVH pattern."
    ),
}

DEMO_SPECIALIST_OPINIONS: dict[str, str] = {
    "Cardiology": (
        "**Key findings (my specialty's view):** ECG shows a left-ventricular "
        "hypertrophy (LVH) pattern in a thin 24-year-old — unusual and important. "
        "Fatigue may be an early cardiac symptom.\n\n"
        "**Possible diagnoses (common → rare):** Athlete's heart (unlikely without "
        "training history); hypertensive heart disease (no hypertension recorded); "
        "hypertrophic cardiomyopathy; infiltrative/storage cardiomyopathy.\n\n"
        "**Rare diseases to consider:** Fabry disease cardiomyopathy — LVH in a "
        "young man plus renal involvement and neuropathic pain is a classic triad. "
        "Cardiac amyloidosis is far less likely at this age.\n\n"
        "**Red flags:** LVH at 24 with rising creatinine suggests a systemic "
        "process, not a primary heart problem.\n\n"
        "**Suggested tests / next steps:** Echocardiogram; cardiac MRI if LVH "
        "confirmed; alpha-galactosidase A activity if storage disease suspected."
    ),
    "Neurology": (
        "**Key findings (my specialty's view):** Lifelong episodic burning pain in "
        "hands and feet (acroparesthesia) triggered by heat and exertion, with "
        "reduced sweating (hypohidrosis) — this points to a small-fiber "
        "neuropathy with autonomic involvement.\n\n"
        "**Possible diagnoses (common → rare):** Idiopathic small-fiber neuropathy; "
        "diabetic neuropathy (no diabetes here); erythromelalgia; hereditary "
        "sensory and autonomic neuropathy.\n\n"
        "**Rare diseases to consider:** Fabry disease is the leading cause of "
        "childhood-onset painful small-fiber neuropathy with hypohidrosis in "
        "males. 'Growing pains' misdiagnosis for years is typical.\n\n"
        "**Red flags:** Childhood onset + autonomic features + family history "
        "argues strongly against an idiopathic label.\n\n"
        "**Suggested tests / next steps:** Skin biopsy for intraepidermal nerve "
        "fiber density; alpha-galactosidase A enzyme assay; genetic testing (GLA gene)."
    ),
    "Medical Genetics": (
        "**Key findings (my specialty's view):** Multi-organ picture (nerves, skin, "
        "gut, kidney, heart) with childhood onset. Family history is decisive: an "
        "affected maternal uncle who died of renal failure and a mildly affected "
        "mother fits X-linked inheritance with a carrier mother.\n\n"
        "**Possible diagnoses (common → rare):** The combination is hard to explain "
        "by common diseases. Storage disorders must be considered.\n\n"
        "**Rare diseases to consider:** Fabry disease (X-linked, GLA gene, "
        "alpha-galactosidase A deficiency) explains every finding: "
        "acroparesthesia, hypohidrosis, angiokeratomas in the 'bathing-trunk' "
        "distribution, GI symptoms, proteinuria, and early LVH. Estimated fit: "
        "very high.\n\n"
        "**Red flags:** Untreated Fabry progresses to renal failure, stroke, and "
        "cardiac death; treatment exists, so missing it is costly.\n\n"
        "**Suggested tests / next steps:** Alpha-galactosidase A activity (blood "
        "spot) in this male patient; confirmatory GLA sequencing; family cascade "
        "screening starting with the mother."
    ),
    "Immunology & Rheumatology": (
        "**Key findings (my specialty's view):** Episodic pain crises with fevers "
        "could mimic an autoinflammatory syndrome, but inflammatory markers are "
        "normal between AND during episodes are not documented as elevated.\n\n"
        "**Possible diagnoses (common → rare):** Juvenile idiopathic arthritis "
        "(no arthritis found); familial Mediterranean fever (episodes lack "
        "serositis and last differently); vasculitis (no purpura — the skin spots "
        "described sound vascular but fixed).\n\n"
        "**Rare diseases to consider:** The fixed dark-red papules around the "
        "umbilicus are more consistent with angiokeratomas (a storage-disease "
        "sign) than any vasculitic rash. Autoinflammatory disease is a mimic "
        "here, not the answer.\n\n"
        "**Red flags:** Normal CRP/ESR with this much symptom burden argues "
        "against primary autoimmune disease.\n\n"
        "**Suggested tests / next steps:** Dermatology review or biopsy of the "
        "skin lesions; defer immunology workup unless storage-disease testing is "
        "negative."
    ),
    "Infectious Disease": (
        "**Key findings (my specialty's view):** Chronic relapsing symptoms over "
        "14+ years without fever pattern, weight loss, exposure history, or "
        "inflammatory markers make a chronic infection very unlikely.\n\n"
        "**Possible diagnoses (common → rare):** Post-infectious neuropathy "
        "(no preceding illness); Whipple disease (GI symptoms, but onset in "
        "childhood argues against); brucellosis (no exposure).\n\n"
        "**Rare diseases to consider:** None from my field fit well. The lifelong "
        "course, family history, and skin findings point away from infection "
        "toward an inherited systemic disease.\n\n"
        "**Red flags:** None infectious. I would not delay the genetic workup for "
        "an infection hunt.\n\n"
        "**Suggested tests / next steps:** No infectious workup needed now; "
        "support enzyme/genetic testing proposed by the board."
    ),
}

DEMO_SYNTHESIS = (
    "**Ranked differential diagnosis:**\n"
    "1. Fabry disease [RARE] — likelihood: high. Childhood-onset burning "
    "acroparesthesia, hypohidrosis, periumbilical angiokeratomas, GI symptoms, "
    "proteinuria with rising creatinine, early LVH, and an X-linked family "
    "pattern (affected maternal uncle, mildly symptomatic mother) — every organ "
    "finding converges on this single diagnosis.\n"
    "2. Hypertrophic cardiomyopathy with coincidental neuropathy — likelihood: "
    "low. Explains the ECG but nothing else.\n"
    "3. Idiopathic small-fiber neuropathy — likelihood: low. A diagnosis of "
    "exclusion that ignores the skin, kidney, and cardiac findings.\n"
    "4. Autoinflammatory syndrome (e.g. FMF) [RARE] — likelihood: low. Mimics "
    "the pain crises but normal inflammatory markers and fixed skin lesions "
    "argue against it.\n\n"
    "**Where the specialists agree:** Neurology, Genetics, and Cardiology "
    "independently converged on Fabry disease; Immunology and Infectious "
    "Disease each ruled their own fields out and deferred to a systemic "
    "inherited disease.\n\n"
    "**Where they disagree:** Only on emphasis — Cardiology wants imaging "
    "confirmation of LVH before anchoring; Genetics considers the clinical "
    "picture already near-diagnostic.\n\n"
    "**Single most valuable next test:** Alpha-galactosidase A enzyme activity "
    "(dried blood spot) — cheap, fast, and in a male patient a low level is "
    "essentially diagnostic; confirm with GLA gene sequencing.\n\n"
    "**Do-not-miss warning:** Untreated Fabry disease leads to renal failure, "
    "stroke, and cardiac death in mid-adulthood — and disease-specific therapy "
    "exists. This patient has already carried the wrong label ('growing pains') "
    "for 14 years."
)
