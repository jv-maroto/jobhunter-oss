// CV template Typst - estilo limpio una columna.
// Marcadores {{...}} se sustituyen por el generador.

#set document(title: {{DOCUMENT_TITLE}}, author: {{NAME_STRING}})
#set page(
  paper: "a4",
  numbering: "1 / 1",
  margin: (top: 1.5cm, bottom: 1.5cm, left: 1.8cm, right: 1.8cm),
)
#set text(font: ("Inter", "Helvetica", "Arial", "Liberation Sans", "Noto Sans"), size: 10pt, lang: {{LANGUAGE}})
#set par(leading: 0.55em, justify: false)

#let section(title) = [
  #v(0.6em)
  #text(weight: "bold", size: 12pt, fill: rgb("#1f2937"))[#title]
  #line(length: 100%, stroke: 0.5pt + rgb("#9ca3af"))
  #v(0.2em)
]

#align(center)[
  #text(size: 20pt, weight: "bold")[{{NAME}}] \
  #text(size: 11pt, fill: rgb("#4b5563"))[{{TITLE}}] \
  #text(size: 9pt)[
    {{CONTACT}} \
    {{LINKS}}
  ]
]

#section({{SUMMARY_HEADING}})
{{SUMMARY}}

#section({{EXPERIENCE_HEADING}})
{{EXPERIENCE}}

#section({{PROJECTS_HEADING}})
{{PROJECTS}}

#section({{SKILLS_HEADING}})
{{SKILLS}}

#section({{EDUCATION_HEADING}})
{{EDUCATION}}

#section({{LANGUAGES_HEADING}})
{{LANGUAGES}}

#section({{CERTIFICATIONS_HEADING}})
{{CERTIFICATIONS}}
