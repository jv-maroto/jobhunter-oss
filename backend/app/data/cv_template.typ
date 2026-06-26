// CV template Typst - estilo limpio una columna.
// Marcadores {{...}} se sustituyen por el generador.

#set document(title: "{{NAME}} - CV", author: "{{NAME}}")
#set page(
  paper: "a4",
  margin: (top: 1.5cm, bottom: 1.5cm, left: 1.8cm, right: 1.8cm),
)
#set text(font: ("Inter", "Helvetica", "Arial"), size: 10pt, lang: "en")
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
    {{EMAIL}} -- {{PHONE}} -- {{LOCATION}} \
    #link("{{GITHUB}}")[GitHub] -- #link("{{LINKEDIN}}")[LinkedIn] -- #link("{{PORTFOLIO}}")[Portfolio]
  ]
]

#section("Summary")
{{SUMMARY}}

#section("Experience")
{{EXPERIENCE}}

#section("Projects")
{{PROJECTS}}

#section("Skills")
{{SKILLS}}

#section("Education")
{{EDUCATION}}
