# Synopsis document template contract

## References and evidence

- Primary format reference: `D:\NESGI  computer BE Mjaor PRoject Synp..docx`
- SHA-256: `52415ce6ec0efd62949097d3562978455be017d8dfa03fdbf4a486d5d0c3d853`
- Page count after Microsoft Word PDF export: 4; DOCX sections: 4.
- Secondary synopsis sample: `D:\3.synopsis template.docx`
- SHA-256: `771dbac114cd0209ce954f8ae341210a6c6e5d79891a382063310a7b50f9d2fd`
- Page count after Microsoft Word PDF export: 8; DOCX sections: 8.
- Reference PDFs and all inspected page PNGs: `.synopsis-docx-work/format-reference.pdf`, `.synopsis-docx-work/format-reference-pages/`, `.synopsis-docx-work/template-reference.pdf`, and `.synopsis-docx-work/template-reference-pages/`.
- Package-part hashes and sizes: `.synopsis-docx-work/package-inventory.csv`.
- Both source DOCX files remain unchanged. The canonical renderer could not find LibreOffice on this Windows host; the references were exported read-only through installed Microsoft Word and all 12 page images were visually inspected.

## Page system and typography

The format document explicitly specifies A4, one-sided printing, 3.5 cm left margin, 2.5 cm top margin, and 1.25 cm right and bottom margins. Its sample title page currently renders on US Letter with different margins; the written A4/margin specification is the applicable submission requirement. Use portrait orientation throughout.

Body text: Times New Roman 12 pt, British English spelling, double spaced. Main headings: 14 pt bold. Subheadings: 12 pt normal. The title-page hierarchy specifies a 24 pt bold project title, 14 pt bold “Project Synopsis”, 12 pt “of Major Project”, 14 pt bold degree, 16 pt branch, and 14 pt student identity. Institution name and Pune location use 16 pt bold. Keep text black on white. The samples use centered title-page text, conventional numbered/bulleted paragraphs, no recurring header/footer, and no page-number furniture. The required body margins override the sample documents' inconsistent actual section margins.

## Content flow

The format document's required order is: title page; table of contents; Introduction (about one page); Rationale (one or two paragraphs); 3–4 Objectives; Literature Review (4–5 papers, about one page); Feasibility Study (no more than one page); Methodology / Planning of Work (no more than one page); Facilities Required (one paragraph); Expected Outcomes (one paragraph); References in IEEE format. The synopsis sample additionally demonstrates a problem definition, proposed system, tools/technologies, expected outcomes, future/research direction, institution logo, and signature spaces. Use relevant software-project sections while omitting unrelated IoT hardware claims.

## Editable slot map

- Title page: project title; project type; degree and branch; `[Student Name]`; `[University Roll No. / PRN]`; `[Class Roll No.]`; `[Batch]`; `[Project Guide Name]`; academic year; institute and department. Keep missing personal or guide data as bracketed editable placeholders. The supplied format document identifies academic year 2026–27 and Computer Engineering.
- Table of contents: real Word TOC field based on heading styles; update when opening/editing in Word.
- Synopsis body: write project-specific Introduction; Problem Definition; Rationale; Objectives (3–4); Proposed System / scope; Literature Review (4–5 verifiable technical papers); Feasibility Study; Methodology / Planning; Facilities Required; Expected Outcomes; IEEE References.
- Optional approvals: leave editable student, guide, and HOD signature/name placeholders only if the page pattern fits without inventing names.
- Logo: reuse the NESGI logo embedded in the supplied references. Do not reuse the NAAC badge or SmartAQ hardware diagram as project content.

## Package and fidelity plan

The primary format file contains the two institutional logo images, one empty contents table, four sections, and no headers or footers. The sample file contains the institutional logo and a project-specific hardware diagram. Their per-part hashes are catalogued in the inventory CSV. Keep both originals untouched. Create the final DOCX as a copy of the primary format reference, reuse its institution logo and typography resources, replace instructional/sample content with editable Jarvis OS synopsis content, and set all resulting sections to the specified A4 page geometry. Remove obsolete instructional text, NAAC badge, SmartAQ text, and unrelated block diagram from the final body.

## Fidelity and correctness gates

- Cover follows the supplied title-page hierarchy and uses the institution logo with editable identity placeholders.
- Required synopsis sections appear in the prescribed order; literature review has four cited primary papers and IEEE reference entries.
- No student name, roll number, guide name, implementation result, performance metric, or capability is invented.
- Jarvis is described as a Python desktop assistant prototype, not a replacement operating system. Distinguish implemented prototype functions from proposed evaluation/future work.
- The final DOCX keeps the written format requirements: A4, specified margins, Times New Roman 12 pt, double spacing, headings as specified, and editable text.
- Refresh the TOC in Word; export through Word to PDF for QA because bundled LibreOffice is unavailable, render all pages to PNG, inspect every page, and revise if any text clips, overlaps, or paginates awkwardly.
