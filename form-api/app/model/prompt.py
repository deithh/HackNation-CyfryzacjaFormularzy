PROMPT = """You digitize a Polish administrative paper form into a web form.
You get the page images and the extracted text (it may contain OCR errors; trust the images).

Return JSON:
- title: the service name as the citizen sees it (max 255 characters).
- pages: thematic pages (for example applicant data, subject of the request, declarations): 1-3 for a short form, at most 6 for a long one, regardless of the number of source pages. No summary page.
- sections: titled groups of 3-8 related fields. A numbered or lettered part with its own heading ("B.2 DANE IDENTYFIKACYJNE WSPÓŁMAŁŻONKA") is its own section, titled without the number. Never a single-field section, except for consents. repeating: true only when the applicant may fill the group several times (another property, children, vehicles).
- fields, one type each:
  TEXT_FIELD: a label followed by a dotted line or empty cell; a sentence with dotted blanks has one field per blank, labelled with the words before it ("w miejscowości ..... przy ulicy ....." gives "Miejscowość", "Ulica").
  TEXTAREA: long text. NUMBER. DATEPICKER: dates the applicant fills in.
  RADIO: one choice from several alternatives (tick boxes or a numbered list such as "Kwotę nadpłaty proszę: 1) ... 2) ..."); CHECKBOX if several may be picked, or a single confirmation. SELECT: drop-down. A blank that belongs to one alternative is a separate field shown only for that option.
  FILE_UPLOADER: each attachment ("w załączeniu ...", "Do wniosku należy dołączyć ..."), one per document, titled with its name. Attachment lists drawn with tick boxes ("☐ kopia mapy") are still FILE_UPLOADER, never CHECKBOX or RADIO.
  TEXT_BLOCK: static text (instructions, fees, the addressee). Keep a GDPR or other information notice together in one TEXT_BLOCK.
  CONSENT_SECTION: declarations or consents the form explicitly asks the applicant to make.

Field properties:
- title: the Polish label exactly as written, without trailing colons, dotted lines or item numbers ("12. Ulica" gives "Ulica"). It must contain words, never a bare "2)". Only TEXT_BLOCK and CONSENT_SECTION may have a blank title.
- Each blank appears once: never repeat a label in one section unless the form has two distinct blanks (for example a conditional alternative).
- required: true, except TEXT_BLOCK and fields the form marks optional ("dane nieobowiązkowe"). A tick box that only marks a neighbouring field as not applicable ("brak numeru lokalu", "nie dotyczy") is not a field: make that neighbouring field required: false.
- validators: PESEL, NIP and REGON fields get the matching validator, postal codes ZIP_CODE, e-mail EMAIL; EPUAP, ADE and SERIAL_NUMBER_ID_CARD only when the field clearly holds that value. Otherwise [].
- options: the choices for RADIO, CHECKBOX and SELECT; otherwise [].
- consents: for CONSENT_SECTION, one {"description": <statement copied word for word>, "required": <whether it must be accepted>} per statement; otherwise []. Never invent wording.
- show_when_*: if a field is shown only after a choice in another field (notes such as "wypełnić tylko w przypadku zaznaczenia ...", "jeśli różni się od ..."), set show_when_field to that field's title, show_when_value to the option, and show_when_page and show_when_section to the page and section that contain it. Otherwise all four are "".

Skip signature lines and anything the authority fills in (case number, stamp area).

Example of the expected output for a different form (shortened):
{"title":"Wniosek o wydanie zaświadczenia","pages":[
 {"title":"Dane wnioskodawcy","sections":[{"title":"Dane wnioskodawcy","repeating":false,"fields":[
   {"type":"TEXT_FIELD","title":"Imię i nazwisko","description":"","required":true,"validators":[],"options":[],"consents":[],"show_when_page":"","show_when_section":"","show_when_field":"","show_when_value":""},
   {"type":"TEXT_FIELD","title":"Kod pocztowy","description":"","required":true,"validators":["ZIP_CODE"],"options":[],"consents":[],"show_when_page":"","show_when_section":"","show_when_field":"","show_when_value":""},
   {"type":"RADIO","title":"Wnioskuję jako","description":"","required":true,"validators":[],"options":["osoba fizyczna","firma"],"consents":[],"show_when_page":"","show_when_section":"","show_when_field":"","show_when_value":""},
   {"type":"TEXT_FIELD","title":"Nazwa firmy","description":"","required":true,"validators":[],"options":[],"consents":[],"show_when_page":"Dane wnioskodawcy","show_when_section":"Dane wnioskodawcy","show_when_field":"Wnioskuję jako","show_when_value":"firma"}]}]},
 {"title":"Oświadczenia","sections":[{"title":"Oświadczenia i zgody","repeating":false,"fields":[
   {"type":"CONSENT_SECTION","title":"Oświadczenia","description":"","required":true,"validators":[],"options":[],"consents":[{"description":"Oświadczam, że podane dane są prawdziwe.","required":true},{"description":"Wyrażam zgodę na kontakt telefoniczny.","required":false}],"show_when_page":"","show_when_section":"","show_when_field":"","show_when_value":""}]}]}]}"""


def build_prompt(extracted: str, instruction: str = "") -> str:
    prompt = PROMPT + "\n\n" + instruction if instruction else PROMPT
    text = extracted.strip()
    if text:
        return prompt + "\n\nExtracted text of the form:\n" + text
    return prompt
