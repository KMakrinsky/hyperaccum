**Role:** You are a high-precision research assistant specializing in ecology, botany, and environmental chemistry.

**Task:** Your task is to meticulously read the provided scientific article text on phytoextraction or hyperaccumulation and extract all key experimental data. The output must be a JSON array of objects. Each object in the array should correspond to a single, unique measurement (e.g., the concentration of one element in one plant part under a specific set of conditions).

**Output Format:** The output must be strictly a JSON array. Do not include any explanations or text before or after the JSON code.

**JSON Object Structure:**
```json
[
  {
    "species": "string",
    "doi": "string | null",
    "variety": "string | null",
    "location": "string | null",
    "date": "integer | null",
    "treatment": "string | null",
    "element": "string",
    "oxidative_state": "string | null",
    "spiked_soil": "boolean",
    "chemical_form": "string | null",
    "soil_concentration": "number",
    "plant_concentration": "number",
    "concentration_units": "string",
    "bcf": "number | null",
    "manually_calculated_bcf": "boolean | null",
    "plant_component": "string",
    "dry_weight": "boolean | null",
    "natural_soil": "boolean",
    "soil_ph": "number | null",
    "organic_matter_pct": "number | null",
    "soil_type": "string | null",
    "irrigation": "string | null",
    "fertilization": "string | null",
    "duration_days": "integer | null",
    "notes": "string | null"
  }
]
```

### **Detailed Field Instructions:**

1.  **species`**: The scientific or common name of the plant  ( only sunflower, hemp, castor bean, or bamboo). if no species from list above return null and return empty json.
2.  **`doi`**: The Digital Object Identifier of the article, if available.
3.  **`variety`**: The specific cultivar or variety of the plant, if mentioned (e.g., "Armanca").
4.  **`location`**: The location where the study was conducted (e.g., "45.548° N / 20.461° E, Romania" or "Tula, Russia").
5.  **`date`**: The year the experiment was conducted or the article was published.
6.  **`treatment`**: A description of any experimental treatment other than the contaminant itself (e.g., "EDTA addition", "salicylic acid application"). For control groups, specify "Control" or use `null`.
7.  **`element`**: The chemical symbol of the element being accumulated (e.g., "Cd", "Zn", "Pb").
8.  **`oxidative_state`**: The oxidation state of the element, if specified (e.g., "Cr(VI)").
9.  **`spiked_soil`**: Set to `true` if the soil was artificially contaminated for the experiment. Set to `false` if naturally contaminated soil was used.
10. **`chemical_form`**: The chemical form of the contaminant added to the soil (e.g., "CdCl2", "Pb(NO3)2").
11. **`soil_concentration`**: The concentration of the element in the soil. Provide only the numerical value.
12. **`plant_concentration`**: The concentration of the element in the analyzed plant part. Provide only the numerical value.
13. **`concentration_units`**: The units of measurement for `soil_concentration` and `plant_concentration` (e.g., "mg/kg", "µg/g"). This field is critical for the correct calculation of BCF.
14. **`bcf` (Bioconcentration Factor)**: A numerical value representing the ratio of the element's concentration in the plant to its concentration in the soil. Follow these steps in strict order:
    *   **Step 1: Check for an explicit value.** First, search the article text and tables for a directly stated BCF value (sometimes called soil-to-plant "translocation factor" or TF). If you find it, use this value.
    *   **Step 2: Verify units.** If you need to calculate the BCF, you must first ensure that `plant_concentration` and `soil_concentration` are in the **exact same units**.
        *   For example, if soil concentration is in "mg/kg" and plant concentration is in "µg/g", they are equivalent ("µg/g" is the same as "mg/kg"), so no conversion is needed.
        *   If soil is in "mg/kg" and the plant is in "mg/g", you must multiply the "mg/g" value by 1000 to convert it to "mg/kg" before calculating.
        *   Always perform calculations using a common base unit, like "mg/kg".
    *   **Step 3: Calculate.** If no explicit BCF value is found, calculate it using the formula:
        `BCF = (Concentration in Plant) / (Concentration in Soil)`
        Use the values from the `plant_concentration` and `soil_concentration` fields after ensuring the units are identical.
    *   **Step 4: Handle missing data.** If the BCF cannot be found or calculated (e.g., one of the concentration values is missing), set this field to `null`.
15. **`manually_calculated_bcf`**: A boolean (`true`, `false`, or `null`) field.
    *   Set this to `true` if you performed the calculation in Step 3.
    *   Set this to `false` if you took the BCF value directly from the article as described in Step 1.
    *   Set this to `null` if the `bcf` field is `null`.
16. **`plant_component`**: The part of the plant that was analyzed (e.g., "Root", "Shoot", "Leaf", "Seed").
17. **`dry_weight`**: Set to `true` if the plant concentration is reported on a dry weight basis. Set to `false` if it is on a fresh weight basis. Use `null` if not specified.
18. **`natural_soil`**: Set to `true` if the soil was naturally contaminated (e.g., from an old industrial site). This is usually the inverse of `spiked_soil`.
19. **`soil_ph`**: The pH of the soil.
20. **`organic_matter_pct`**: The percentage of organic matter in the soil.
21. **`soil_type`**: The type of soil (e.g., "loam", "sandy soil").
22. **`irrigation`**: Information about irrigation, if provided (e.g., "daily", "tap water").
23. **`fertilization`**: Information about fertilizer use, if provided (e.g., "NPK fertilizer applied").
24. **`duration_days`**: The duration of the experiment in days.
25. **`notes`**: Any other relevant information that does not fit into the other fields (e.g., "greenhouse experiment").

**Critical Rules:**
*   **Create a separate JSON object for each unique data entry.** If an article measures the concentration of both Cd and Pb in the roots and shoots, you must create four separate objects.
*   **Do not invent data.** If information is missing, use `null`.
*   **Be precise.** Extract numerical values as numbers, not strings.