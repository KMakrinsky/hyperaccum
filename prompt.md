**Task:** Extract detailed experimental data from the provided scientific article on phytoextraction and hyperaccumulation. Structure the extracted information into a JSON format according to the highly granular schema below.

**Instructions:**

1.  **Thoroughly analyze the entire article**: Pay close attention to the abstract, materials and methods, results, tables, and figures to capture all details.
2.  **Populate the JSON schema**: Fill in all fields based on the information from the article. If specific information is not available, use `null` as the value.
3.  **For the `experimental_groups` array**:
    *   Create a distinct JSON object for each unique experimental group. A group is defined by a unique combination of plant type and the treatments applied.
    *   **Crucially, specify the `biological_material` (the plant species/variety) within each group object.** This is essential for experiments comparing multiple plant types.
    *   Clearly identify the control group by setting `is_control: true`.
    *   For measurements within `plant_measurements`, use the `biomass_measurements` and `metal_uptake` arrays. For each entry, specify the `plant_part` (e.g., "root", "shoot", "leaf", "stem") as reported in the paper. This allows for flexible and detailed data capture.
4.  **For the `results` section**:
    *   In `key_findings_summary`, provide a concise summary of the study's main outcomes.
    *   In the `hyperaccumulation_potential` array, for each key element, calculate the following metrics based on the extracted data. Specify which experimental group (`group_id`) is used for the calculation, focusing on the most relevant treatment groups.
        *   **Root Bioconcentration Factor (Root BCF)**: `(Metal concentration in roots) / (Initial metal concentration in soil)`
        *   **Shoot Bioconcentration Factor (Shoot BCF)**: `(Metal concentration in shoots) / (Initial metal concentration in soil)`
        *   **Translocation Factor (TF)**: `(Metal concentration in shoots) / (Metal concentration in roots)`
    *   In the `conclusion` field, interpret these values. A plant is a strong candidate for phytoextraction if **Shoot BCF > 1** and **TF > 1**.

DO NOT ADD ANY ADDITIONAL WORDS AND SYMBOLS! ONLY RAW JSON!

**JSON Schema to be filled:**

{
  "general_info": {
    "doi": "String",
    "title": "String",
    "authors": ["String"],
    "year": "Integer"
  },
  "study_objective": "String",
  "experimental_design": {
    "study_type": "String (e.g., pot experiment, field trial, hydroponics)",
    "duration_days": "Integer",
    "description": "String"
  },
  "growth_medium": {
    "medium_type": "String (e.g., soil, hydroponic solution)",
    "soil_properties": {
      "soil_type": "String",
      "ph": "Float",
      "organic_matter_percent": "Float",
      "contaminants": [
        {
          "element": "String (e.g., Cd, Pb, Zn)",
          "initial_concentration": "Float",
          "units": "String (e.g., mg/kg)"
        }
      ],
      "contamination_type": "String (e.g., artificially spiked, naturally contaminated)"
    },
    "hydroponic_solution_composition": "String"
  },
  "experimental_groups": [
    {
      "group_id": "String",
      "is_control": "Boolean",
      "description": "String (e.g., 'Control for Plant A', 'Plant B with 5 mmol/kg EDTA')",
      "biological_material": {
        "species": "String",
        "variety": "String"
      },
      "treatments": [
        {
          "substance": "String (e.g., EDTA, citric acid, NPK fertilizer)",
          "concentration": "Float",
          "units": "String (e.g., mmol/kg, g/kg)"
        }
      ],
      "plant_measurements": {
        "biomass_measurements": [
          {
            "plant_part": "String (e.g., 'root', 'shoot', 'leaf')",
            "dry_weight_g": "Float"
          }
        ],
        "metal_uptake": [
          {
            "plant_part": "String (e.g., 'root', 'shoot', 'leaf')",
            "element": "String",
            "concentration": "Float",
            "units": "String (e.g., mg/kg)"
          }
        ]
      }
    }
  ],
  "results": {
    "key_findings_summary": "String",
    "hyperaccumulation_potential": [
      {
        "element": "String",
        "based_on_group_id": "String",
        "calculation_inputs": {
            "initial_soil_concentration": "Float",
            "root_concentration": "Float",
            "shoot_concentration": "Float"
        },
        "root_bioconcentration_factor": "Float",
        "shoot_bioconcentration_factor": "Float",
        "translocation_factor": "Float",
        "conclusion": "String"
      }
    ]
  }
}