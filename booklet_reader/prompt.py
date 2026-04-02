import json


def build_prompt(performers):
    performer_lines = []
    for p in performers:
        aliases_by_instrument = []
        for inst in p["instruments"]:
            aliases = [a.strip() for a in inst["names"].split("/")]
            aliases_by_instrument.append(
                f"  - Instrument aliases: {' / '.join(aliases)} (canonical name: {aliases[0]})"
            )
        performer_lines.append(
            f"- {p['name']}\n" + "\n".join(aliases_by_instrument)
        )

    performers_block = "\n".join(performer_lines)

    output_schema = json.dumps(
        [
            {
                "event_name": "string — name of the event/competition/festival/concert",
                "performance_date": "string — ISO 8601 date (YYYY-MM-DD) of this specific performance",
                "performer": "string — full name of the matched performer (use exact name from the list above)",
                "instrument": "string — canonical instrument name (first alias from the list above)",
                "pieces": [
                    {
                        "composer": "string — composer name",
                        "title": "string — piece title, including movement/opus if mentioned",
                    }
                ],
                "teacher": "string or null — teacher name if mentioned in the document",
                "accompanist": "string or null — accompanist name if mentioned in the document",
                "co_performers": [
                    {
                        "name": "string — name of the co-performer",
                        "instrument": "string — instrument of the co-performer",
                    }
                ],
            }
        ],
        indent=2,
        ensure_ascii=False,
    )

    return f"""You are analyzing a music program booklet (műsorfüzet). These pages are from a document about a music competition, concert, recital, festival, or other public performance.

Your task: find any performances by the following performers and extract structured data.

=== PERFORMERS TO SEARCH FOR ===
{performers_block}

=== INSTRUCTIONS ===
1. Search the entire document for any of the listed performer names.
2. Be flexible with name matching: the document may omit middle names, use abbreviations, or use slightly different forms. Match on family name + first name even if middle names differ.
3. For each match, extract the specific performance date. The document may have a schedule at the beginning showing which day/time slot each category performs — use this to determine the exact date, not just the event date range.
4. Identify the instrument played. Use the canonical name (first alias) from the performer list above.
5. List ALL pieces performed (composer + title). Include opus numbers, movement names, and any other details mentioned.
6. If a teacher (felkészítő tanár, tanár) is mentioned for this performer's entry, include it.
7. If an accompanist (kísérő, zongorakísérő) is mentioned, include it.
8. If the performer is part of a duo, trio, quartet, or other ensemble, list the other members as co_performers with their instruments. If solo, use an empty array.
9. If a performer appears in multiple entries (e.g., different categories or rounds), return a separate object for each appearance.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON array. No markdown, no explanation, no code fences. Just the JSON.

If no matches are found, return an empty array: []

Schema:
{output_schema}

=== IMPORTANT ===
- Use the EXACT performer name from the list above in the "performer" field, not the form found in the document.
- Use the canonical instrument name (first alias) in the "instrument" field.
- performance_date must be ISO 8601 (YYYY-MM-DD). If you cannot determine the exact date, use the first day of the event.
- pieces must always be an array, even for a single piece.
- co_performers must always be an array, empty if solo.
- teacher and accompanist should be null if not mentioned in the document.
"""


def build_retry_prompt(previous_response):
    return f"""Your previous response could not be parsed as valid JSON. Here is what you returned:

{previous_response}

Please try again. Return ONLY a valid JSON array with all required fields populated with data from the document:
- event_name (string)
- performance_date (YYYY-MM-DD string)
- performer (string)
- instrument (string)
- pieces (array of objects with composer and title)
- teacher (string or null)
- accompanist (string or null)
- co_performers (array of objects with name and instrument)

No markdown fences, no explanation. Just the JSON array."""
