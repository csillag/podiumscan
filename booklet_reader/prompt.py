import json


def build_prompt(performers, comment=None):
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

    comment_block = ""
    if comment:
        comment_block = f"""
=== ADDITIONAL GUIDANCE ===
{comment}
"""

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
   IMPORTANT: In competition booklets, the repertoire often does NOT appear next to the performer's name. Instead, each category/age group (korcsoport) has its own "Művek" (pieces) section listing available pieces by code — typically a number (1, 2, 3...), a letter (A, B...), and a Roman numeral (I, II...), or a combined code like C-III. Each performer's entry then references these codes (e.g., "Műsor: 3, B, I" means they perform piece #3, piece B, and piece I from THAT category's piece list).
   You MUST resolve these codes to full composer and title by looking up the piece list belonging to the SAME category where the performer appears. Each category has its own separate piece list — do NOT use a piece list from a different category. If you cannot resolve a code, explain why in plain text instead of returning empty pieces.
6. If a teacher (felkészítő tanár, tanár) is mentioned for this performer's entry, include it.
7. If an accompanist (kísérő, zongorakísérő) is mentioned, include it.
8. If the performer is part of a duo, trio, quartet, or other ensemble, list the other members as co_performers with their instruments. If solo, use an empty array.
9. If a performer appears in multiple entries (e.g., different categories or rounds), return a separate object for each appearance.
10. If you cannot extract the requested data — for example, because the document is unreadable, the format is unrecognizable, or none of the listed performers appear — do NOT return malformed JSON. Instead, return a plain text explanation of what went wrong and what you were able to see in the document.

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
- If the composer of a piece is unknown or cannot be determined, use "<UNKNOWN>" as the composer value.
{comment_block}"""


def build_retry_prompt(previous_response):
    return f"""Your previous response could not be parsed as valid JSON. Here is what you returned:

{previous_response}

Please return ONLY valid JSON — no extra text before or after the array. The response must be parseable by json.loads().

If you found matching performers, return a JSON array with all required fields (event_name, performance_date, performer, instrument, pieces, teacher, accompanist, co_performers). Every field must be populated with actual data from the document — do not return empty pieces arrays if the information is available somewhere in the document (e.g., in a separate repertoire list for that category).

If you genuinely found no matches, return an empty array: []

If you cannot extract the data due to document quality or format issues, return an empty array [] — do not fabricate data."""
