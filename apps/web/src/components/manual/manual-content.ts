import type { AppLanguage } from "@/lib/app-settings";

export type ManualSection = {
  id: string;
  title: string;
  /** Where in the app this lives, e.g. "Sidebar → Analyze". */
  where: string;
  /** One sentence: what this feature is for. */
  purpose: string;
  /** Ordered workflow steps. */
  steps: string[];
  /** Hard facts: limits, statuses, roles. */
  facts: string[];
};

export type ManualContent = {
  intro: string;
  readTime: string;
  quickStart: string[];
  sections: ManualSection[];
  boundariesTitle: string;
  boundaries: string[];
  glossaryTitle: string;
  glossary: { term: string; meaning: string }[];
};

const en: ManualContent = {
  intro:
    "CV Analyzer is recruiter decision support. It reads a CV, shows what the document literally says, flags what needs a human check, and helps you build an anonymized candidate profile. It never makes a hiring judgment for you.",
  readTime: "About 5 minutes to read. Everything you can do in the app is listed here.",
  quickStart: [
    "Sign in with your Idego Google account.",
    "Analyze: drop PDF or DOCX files, click Analyze files, wait for Completed, open the report.",
    "Read Needs attention first, then Worth knowing. Every finding shows the CV evidence it is based on.",
    "Optionally run Company, Education, or LinkedIn research from the report.",
    "Profile Builder: convert the CV into an editable profile, hide personal fields, export DOCX or PDF.",
    "Rate the result (Helpful / Needs improvement) so the team can improve the tool.",
  ],
  sections: [
    {
      id: "analyze",
      title: "Analyze a CV",
      where: "Sidebar → Analyze",
      purpose: "Turn one or many CVs into structured reports with findings backed by quotes from the document.",
      steps: [
        "Drag and drop files onto the upload area, or click it to select. You can add several files at once.",
        "Remove a file with the X next to its name. Reset clears the whole queue.",
        "Click Analyze files. Files run one after another; each shows Waiting, Analyzing, Completed, or Failed.",
        "Cancel stops the batch. Files not yet processed go back to the queue.",
        "When a file reaches Completed it appears under Recent analyses. Click it to open the report.",
      ],
      facts: [
        "Accepted formats: PDF and DOCX only. Scanned PDFs without a text layer are rejected with an explicit message.",
        "Default maximum file size: 20 MB (deployment setting).",
        "Typical processing time: about 35 seconds per CV. The card shows elapsed and estimated remaining time.",
        "A report marked Partial means at least one section could not be analyzed confidently. Read it with extra care.",
        "Analysis language (Settings) controls the language of newly generated report text.",
      ],
    },
    {
      id: "report",
      title: "Read a report",
      where: "Analyze → Recent analyses → open an analysis",
      purpose: "Review what the CV states and what deserves a follow-up question, with the original document beside it.",
      steps: [
        "Left: the report. Right: the original CV preview. Drag the divider to resize, or use Show CV / Hide CV.",
        "CV overview lists Contact, Experience, Education, and Certifications exactly as extracted from the CV.",
        "Needs attention lists inconsistencies to verify with the candidate. Worth knowing lists useful context.",
        "Hover or click a finding to see Why it matters, What to check, and Evidence (verbatim CV excerpts).",
        "Copy link creates a read-only share link for a colleague.",
        "Estimated report AI cost shows what this analysis cost in USD and PLN.",
      ],
      facts: [
        "Contact shows declared location, GeoNames-resolved city and country, postal code consistency, and an Inside the EU / Outside the EU note based on the declared address.",
        "Typical findings: declared city and country mismatch, phone country differs from declared country, possible email-domain typo, missing CV information, ambiguous or unresolved location.",
        "Every value in the report has literal evidence in the CV. If the CV does not say it, the report does not show it.",
        "Shared links open the report read-only. If the original CV has been purged by retention, the preview says so.",
      ],
    },
    {
      id: "research",
      title: "Public research (Company, Education, LinkedIn)",
      where: "Inside a report, next to an employer, school, or the candidate header",
      purpose: "Check whether an employer or school has a public footprint, and find possible public LinkedIn profiles.",
      steps: [
        "Click Run research next to an employer or school. Results show Confidence: high / medium / low and source links with readable hostnames.",
        "Company research reports the official website, reported offices, and operating dates when found.",
        "LinkedIn profile search lists Possible profile 1, 2, … with Open profile links, photo visibility, and connection count.",
        "Search with Google and Search on LinkedIn open a manual search in a new tab.",
        "Settings → Run research automatically triggers selected research kinds right after each analysis.",
      ],
      facts: [
        "Statuses: Public company footprint found, Public sources conflict, Not confirmed in public sources, Not enough public information.",
        "LinkedIn search only suggests possible public profiles. It does not verify identity.",
        "Research runs only on accepted, evidence-supported subjects from the report.",
        "Research timed out means you can safely click again. Results are cached per analysis.",
        "Research is available only when the deployment has it enabled (see Settings → System health).",
      ],
    },
    {
      id: "recent",
      title: "Recent analyses",
      where: "Sidebar → Analyze, below the upload area",
      purpose: "Find and reopen previous reports.",
      steps: [
        "Search by candidate name or filename.",
        "Five rows show by default. Show more expands the list; Show fewer collapses it.",
        "Delete analysis removes one report and its stored CV. Click a second time to confirm.",
      ],
      facts: [
        "New badge marks analyses created in your current session. Partial badge marks incomplete reports.",
        "Analyses are purged automatically after the retention window (Settings → Data retention).",
      ],
    },
    {
      id: "feedback",
      title: "Rate a result",
      where: "Inside a report, on the whole report or on a single finding",
      purpose: "Tell the team when a result is wrong or helpful so the analyzer can be improved.",
      steps: [
        "Click Rate result, Report a problem, or Give feedback.",
        "Choose Helpful or Needs improvement and optionally write a comment (up to 300 characters).",
        "Click Send feedback. Sent! confirms it reached the team inbox.",
      ],
      facts: [
        "You must choose a rating or write a comment; empty feedback is rejected.",
        "Feedback attaches the relevant report section and CV excerpt so reviewers see the context.",
        "A feedback owner can turn feedback collection off for the deployment.",
      ],
    },
    {
      id: "profile-builder",
      title: "Profile Builder",
      where: "Sidebar → Profile Builder",
      purpose: "Convert a CV into an editable candidate profile and export an anonymized DOCX or PDF for a client.",
      steps: [
        "Drop PDF or DOCX files and start conversion. Statuses: Waiting, Converting, Completed, Failed. Cancel stops the batch.",
        "Open a finished profile from Recent profiles. Edit personal data, headline, summary, skills, experience, education, languages, certifications, additional sections, and team custom fields.",
        "Anonymization: toggle Hide first name, last name, email, phone, location, links; Hide employer names; Hide school and university names. Hide all / Show all apply to every field.",
        "Pick a template. The preview on the right is the real PDF export, so what you see is what the client gets.",
        "Use AI helpers: Add a short summary (optionally with a job description), per-section AI actions, or translate the profile.",
        "Download DOCX (editable) or PDF. Edits autosave; wait for Saved before leaving.",
      ],
      facts: [
        "Limits per batch: 10 files, 10 MB per file. Typical conversion time: about 40 seconds per CV.",
        "Anonymization hides fields in the export only. The saved profile keeps the full data.",
        "Also check free-text descriptions for names before sharing; only structured fields are hidden automatically.",
        "AI proposals are validated before they touch your profile. If validation fails, the profile stays unchanged.",
        "The original uploaded CV is not stored by Profile Builder; only the extracted profile is.",
        "If PDF export is unavailable, download DOCX instead.",
      ],
    },
    {
      id: "templates",
      title: "Templates and preferences",
      where: "Profile Builder → template picker → Template Creator; Settings → Profile Builder",
      purpose: "Control how exported profiles look and set your personal defaults.",
      steps: [
        "IDEGO Default is the built-in shared template. Create a new one from the template picker.",
        "Template Creator: drag blocks onto the A4 page (left, full, right lanes), toggle block visibility with the eye icon, rename headings, set brand colors, typography, header, and lists, and place one logo (PNG, JPG, WebP, SVG).",
        "Set visibility to Private (only you) or Shared (whole team). New templates are Private by default.",
        "Settings → Profile Builder: default template, date format, automatic summary, default anonymization, export filename pattern, and whether to list technologies from work experience. Click Save my preferences.",
        "Settings → Profile fields for the team: add custom fields (Text, Number, Yes-No, Date, Select) that appear in every profile.",
      ],
      facts: [
        "Filename patterns: candidate-profile, candidate-template, candidate-profile-date, or custom with {name} {first_name} {last_name} {template} {date}.",
        "Back warns you if the template has unsaved changes.",
      ],
    },
    {
      id: "profiles",
      title: "Profiles catalog",
      where: "Sidebar → Profile Builder → Profiles (or /profiles)",
      purpose: "Browse every saved candidate profile.",
      steps: [
        "Search by candidate, filename, or template.",
        "Click a row to edit or export. Convert CV starts a new conversion.",
        "Delete removes the profile permanently after a second confirming click.",
      ],
      facts: ["Rows show candidate name (or Unnamed candidate), source filename, template, and last update time."],
    },
    {
      id: "dashboard",
      title: "Dashboard",
      where: "Sidebar → Dashboard",
      purpose: "See how much AI the team uses and what it costs.",
      steps: [
        "Reports processed, tokens (Total, Average, Prompt, Cached, Completion), and Estimated cost with a USD / PLN toggle.",
        "Usage by operation breaks cost down: CV analysis, employment and education passes, company / education / LinkedIn research, Profile Builder conversion, summary, AI actions, translation.",
      ],
      facts: ["Costs are estimates based on token counts. The dashboard covers the whole deployment, not only your analyses."],
    },
    {
      id: "inbox",
      title: "Feedback inbox (reviewers and owners only)",
      where: "Sidebar → Feedback (visible only if you have access)",
      purpose: "Triage feedback sent from reports.",
      steps: [
        "Filter by status: All, New, Reviewing, Planned, Resolved, Won't fix.",
        "Open an item to see the rating, comment, author, and context (Show CV excerpt, Show report section, Error details).",
        "Change the status, add a Team note, or delete the item (click twice).",
        "Manage access (owners only): grant Reviewer or Owner by company email, or revoke access.",
      ],
      facts: [
        "Reviewer: reads and handles feedback. Owner: also manages access, feedback collection, and deployment-wide retention.",
        "At least one owner must always remain.",
      ],
    },
    {
      id: "settings",
      title: "Settings",
      where: "Sidebar → Settings",
      purpose: "Personal display options plus deployment-wide data controls.",
      steps: [
        "UI language and Analysis language: English or Polski, independently.",
        "Public research: turn web research on or off, preview findings on hover, expand sections by default, run research automatically per kind.",
        "Data retention: how many days completed analyses and stored CVs are kept (1 to 3650). Owners only; applies to every user.",
        "Delete all analyses permanently removes every saved analysis and stored CV for the deployment. Confirm in the dialog.",
        "System health: Ready or Needs attention, with Technical details per capability (database, GeoNames, analysis, research kinds, Profile Builder, PDF export, feedback). Use Refresh status after an outage.",
      ],
      facts: [
        "Language, hover, and research toggles are saved in your browser only.",
        "Retention and Delete all affect the whole team. Ask a feedback owner if the controls are disabled for you.",
      ],
    },
  ],
  boundariesTitle: "What the app does not do",
  boundaries: [
    "It does not verify identity, honesty, residence, physical location, nationality, or work eligibility. The EU note and location checks describe the declared address only.",
    "It does not score, rank, or recommend candidates. Findings are questions to ask, not verdicts.",
    "It does not invent data. Every profile, employment, and education value needs literal evidence in the CV.",
    "It does not send CV content to public search. Only accepted, evidence-supported names of employers, schools, and candidates are researched.",
    "It does not keep files forever. Analyses follow the retention window, and Profile Builder never stores the original CV file.",
  ],
  glossaryTitle: "Glossary",
  glossary: [
    { term: "Evidence", meaning: "A verbatim excerpt from the CV that supports a value or finding." },
    { term: "Needs attention", meaning: "Inconsistency or gap you should verify with the candidate." },
    { term: "Worth knowing", meaning: "Helpful context that is not a problem by itself." },
    { term: "Partial", meaning: "Report where at least one section could not be analyzed confidently." },
    { term: "Confidence", meaning: "How strongly public sources agree with the CV: high, medium, or low." },
    { term: "Anonymization", meaning: "Hiding selected fields in the exported profile without changing the saved data." },
    { term: "Retention", meaning: "Number of days completed analyses and their CVs are kept before automatic deletion." },
    { term: "Owner / Reviewer", meaning: "Feedback roles. Owners also manage access, retention, and feedback collection." },
  ],
};

const pl: ManualContent = {
  intro:
    "CV Analyzer wspiera decyzje rekrutera. Czyta CV, pokazuje, co dokument dosłownie zawiera, oznacza to, co wymaga sprawdzenia przez człowieka, i pomaga zbudować zanonimizowany profil kandydata. Nigdy nie podejmuje decyzji rekrutacyjnej za Ciebie.",
  readTime: "Około 5 minut czytania. Znajdziesz tu wszystko, co można zrobić w aplikacji.",
  quickStart: [
    "Zaloguj się kontem Google Idego.",
    "Analizuj: przeciągnij pliki PDF lub DOCX, kliknij Analizuj pliki, poczekaj na status Ukończono i otwórz raport.",
    "Najpierw czytaj Wymaga uwagi, potem Warto wiedzieć. Każde ustalenie pokazuje fragment CV, na którym się opiera.",
    "Opcjonalnie uruchom z raportu research firmy, uczelni lub LinkedIn.",
    "Profile Builder: przekonwertuj CV na edytowalny profil, ukryj dane osobowe, wyeksportuj DOCX lub PDF.",
    "Oceń wynik (Pomocny / Do poprawy), aby zespół mógł ulepszać narzędzie.",
  ],
  sections: [
    {
      id: "analyze",
      title: "Analiza CV",
      where: "Menu → Analizuj",
      purpose: "Zamień jedno lub wiele CV w uporządkowane raporty z ustaleniami popartymi cytatami z dokumentu.",
      steps: [
        "Przeciągnij pliki na pole wgrywania lub kliknij je, aby wybrać. Możesz dodać kilka plików naraz.",
        "Usuń plik znakiem X obok nazwy. Wyczyść opróżnia całą kolejkę.",
        "Kliknij Analizuj pliki. Pliki przetwarzane są po kolei; każdy ma status Oczekuje, Analiza, Ukończono lub Błąd.",
        "Anuluj zatrzymuje partię. Nieprzetworzone pliki wracają do kolejki.",
        "Ukończony plik pojawia się w Ostatnich analizach. Kliknij go, aby otworzyć raport.",
      ],
      facts: [
        "Akceptowane formaty: tylko PDF i DOCX. Skany bez warstwy tekstowej są odrzucane z jasnym komunikatem.",
        "Domyślny limit rozmiaru pliku: 20 MB (ustawienie wdrożenia).",
        "Typowy czas przetwarzania: około 35 sekund na CV. Karta pokazuje czas, który upłynął, i szacowany pozostały.",
        "Raport oznaczony Częściowy oznacza, że co najmniej jedna sekcja nie została przeanalizowana pewnie. Czytaj go uważniej.",
        "Język analizy (Ustawienia) decyduje o języku nowo generowanego tekstu raportu.",
      ],
    },
    {
      id: "report",
      title: "Czytanie raportu",
      where: "Analizuj → Ostatnie analizy → otwórz analizę",
      purpose: "Sprawdź, co CV deklaruje i co wymaga dopytania, mając obok oryginalny dokument.",
      steps: [
        "Lewa strona: raport. Prawa: podgląd oryginalnego CV. Przeciągnij separator, aby zmienić proporcje, lub użyj Pokaż CV / Ukryj CV.",
        "Przegląd CV pokazuje Kontakt, Doświadczenie, Edukację i Certyfikaty dokładnie tak, jak zostały wyciągnięte z CV.",
        "Wymaga uwagi zbiera niespójności do zweryfikowania z kandydatem. Warto wiedzieć zbiera przydatny kontekst.",
        "Najedź lub kliknij ustalenie, aby zobaczyć Dlaczego to ważne, Co sprawdzić i Dowody (dosłowne fragmenty CV).",
        "Kopiuj link tworzy link tylko do odczytu dla współpracownika.",
        "Szacowany koszt AI raportu pokazuje koszt tej analizy w USD i PLN.",
      ],
      facts: [
        "Kontakt pokazuje deklarowaną lokalizację, miasto i kraj rozpoznane przez GeoNames, spójność kodu pocztowego oraz informację W UE / Poza UE na podstawie deklarowanego adresu.",
        "Typowe ustalenia: niespójne miasto i kraj, kraj numeru telefonu inny niż deklarowany, możliwa literówka w domenie e-mail, brakujące informacje w CV, niejednoznaczna lub nierozpoznana lokalizacja.",
        "Każda wartość w raporcie ma dosłowny dowód w CV. Jeśli CV czegoś nie mówi, raport tego nie pokazuje.",
        "Udostępniony link otwiera raport tylko do odczytu. Jeśli oryginalne CV zostało usunięte przez retencję, podgląd o tym informuje.",
      ],
    },
    {
      id: "research",
      title: "Research publiczny (firma, uczelnia, LinkedIn)",
      where: "W raporcie, obok pracodawcy, uczelni lub nagłówka kandydata",
      purpose: "Sprawdź, czy pracodawca lub uczelnia ma publiczny ślad, i znajdź możliwe publiczne profile LinkedIn.",
      steps: [
        "Kliknij Uruchom research obok pracodawcy lub uczelni. Wynik pokazuje Pewność: wysoka / średnia / niska oraz linki do źródeł z czytelnymi nazwami domen.",
        "Research firmy podaje oficjalną stronę, zgłaszane biura i daty działalności, jeśli je znaleziono.",
        "Wyszukiwanie profilu LinkedIn wypisuje Możliwy profil 1, 2, … z linkiem Otwórz profil, widocznością zdjęcia i liczbą kontaktów.",
        "Szukaj w Google i Szukaj na LinkedIn otwierają ręczne wyszukiwanie w nowej karcie.",
        "Ustawienia → Uruchamiaj research automatycznie odpala wybrane rodzaje researchu zaraz po każdej analizie.",
      ],
      facts: [
        "Statusy: Znaleziono publiczny ślad firmy, Źródła publiczne są sprzeczne, Niepotwierdzone w źródłach publicznych, Za mało informacji publicznych.",
        "Wyszukiwanie LinkedIn tylko podpowiada możliwe publiczne profile. Nie weryfikuje tożsamości.",
        "Research obejmuje tylko zaakceptowane, poparte dowodami podmioty z raportu.",
        "Research przekroczył limit czasu oznacza, że można bezpiecznie kliknąć ponownie. Wyniki są zapamiętywane dla analizy.",
        "Research działa tylko, gdy wdrożenie ma go włączonego (patrz Ustawienia → Stan systemu).",
      ],
    },
    {
      id: "recent",
      title: "Ostatnie analizy",
      where: "Menu → Analizuj, pod polem wgrywania",
      purpose: "Znajdź i otwórz ponownie wcześniejsze raporty.",
      steps: [
        "Szukaj po nazwisku kandydata lub nazwie pliku.",
        "Domyślnie widać pięć wierszy. Pokaż więcej rozwija listę; Pokaż mniej ją zwija.",
        "Usuń analizę kasuje jeden raport i zapisane CV. Kliknij drugi raz, aby potwierdzić.",
      ],
      facts: [
        "Znacznik Nowe oznacza analizy z bieżącej sesji. Znacznik Częściowy oznacza niekompletne raporty.",
        "Analizy są usuwane automatycznie po okresie retencji (Ustawienia → Retencja danych).",
      ],
    },
    {
      id: "feedback",
      title: "Ocena wyniku",
      where: "W raporcie, dla całego raportu lub pojedynczego ustalenia",
      purpose: "Daj znać zespołowi, gdy wynik jest błędny lub pomocny, aby analizator mógł być ulepszany.",
      steps: [
        "Kliknij Oceń wynik, Zgłoś problem lub Przekaż opinię.",
        "Wybierz Pomocny lub Do poprawy i opcjonalnie napisz komentarz (do 300 znaków).",
        "Kliknij Wyślij. Wysłano! potwierdza, że opinia trafiła do skrzynki zespołu.",
      ],
      facts: [
        "Musisz wybrać ocenę lub napisać komentarz; pusty feedback jest odrzucany.",
        "Feedback zapisuje powiązaną sekcję raportu i fragment CV, aby recenzenci widzieli kontekst.",
        "Właściciel feedbacku może wyłączyć zbieranie feedbacku dla całego wdrożenia.",
      ],
    },
    {
      id: "profile-builder",
      title: "Profile Builder",
      where: "Menu → Profile Builder",
      purpose: "Przekonwertuj CV na edytowalny profil kandydata i wyeksportuj zanonimizowany DOCX lub PDF dla klienta.",
      steps: [
        "Przeciągnij pliki PDF lub DOCX i uruchom konwersję. Statusy: Oczekuje, Konwersja, Ukończono, Błąd. Anuluj zatrzymuje partię.",
        "Otwórz gotowy profil z Ostatnich profili. Edytuj dane osobowe, nagłówek, podsumowanie, umiejętności, doświadczenie, edukację, języki, certyfikaty, sekcje dodatkowe i pola zespołowe.",
        "Anonimizacja: przełącz Ukryj imię, nazwisko, e-mail, telefon, lokalizację, linki; Ukryj nazwy pracodawców; Ukryj nazwy szkół i uczelni. Ukryj wszystko / Pokaż wszystko działa na każde pole.",
        "Wybierz szablon. Podgląd po prawej to prawdziwy eksport PDF, więc widzisz dokładnie to, co dostanie klient.",
        "Użyj pomocy AI: Dodaj krótkie podsumowanie (opcjonalnie z opisem stanowiska), akcje AI dla sekcji lub tłumaczenie profilu.",
        "Pobierz DOCX (edytowalny) lub PDF. Zmiany zapisują się automatycznie; przed wyjściem poczekaj na Zapisano.",
      ],
      facts: [
        "Limity partii: 10 plików, 10 MB na plik. Typowy czas konwersji: około 40 sekund na CV.",
        "Anonimizacja ukrywa pola tylko w eksporcie. Zapisany profil zachowuje pełne dane.",
        "Przed udostępnieniem sprawdź też opisy tekstowe pod kątem nazw; automatycznie ukrywane są tylko pola strukturalne.",
        "Propozycje AI są walidowane, zanim zmienią profil. Jeśli walidacja się nie powiedzie, profil pozostaje bez zmian.",
        "Profile Builder nie przechowuje oryginalnego pliku CV; zapisuje tylko wyciągnięty profil.",
        "Jeśli eksport PDF jest niedostępny, pobierz DOCX.",
      ],
    },
    {
      id: "templates",
      title: "Szablony i preferencje",
      where: "Profile Builder → wybór szablonu → Kreator szablonu; Ustawienia → Profile Builder",
      purpose: "Kontroluj wygląd eksportowanych profili i ustaw swoje domyślne wartości.",
      steps: [
        "IDEGO Default to wbudowany szablon współdzielony. Nowy szablon tworzysz z listy wyboru szablonu.",
        "Kreator szablonu: przeciągaj bloki na stronę A4 (kolumna lewa, pełna, prawa), przełączaj widoczność bloku ikoną oka, zmieniaj nagłówki, kolory marki, typografię, nagłówek i listy oraz umieść jedno logo (PNG, JPG, WebP, SVG).",
        "Ustaw widoczność Prywatny (tylko Ty) lub Współdzielony (cały zespół). Nowe szablony są domyślnie Prywatne.",
        "Ustawienia → Profile Builder: domyślny szablon, format dat, automatyczne podsumowanie, domyślna anonimizacja, wzór nazwy pliku oraz czy wypisywać technologie z doświadczenia. Kliknij Zapisz moje preferencje.",
        "Ustawienia → Pola profilu dla zespołu: dodaj pola własne (Tekst, Liczba, Tak-Nie, Data, Wybór), które pojawią się w każdym profilu.",
      ],
      facts: [
        "Wzory nazw plików: kandydat-profile, kandydat-szablon, candidate-profile-data lub własny z {name} {first_name} {last_name} {template} {date}.",
        "Wróć ostrzega, jeśli szablon ma niezapisane zmiany.",
      ],
    },
    {
      id: "profiles",
      title: "Katalog profili",
      where: "Menu → Profile Builder → Profile (lub /profiles)",
      purpose: "Przeglądaj wszystkie zapisane profile kandydatów.",
      steps: [
        "Szukaj po kandydacie, nazwie pliku lub szablonie.",
        "Kliknij wiersz, aby edytować lub eksportować. Konwertuj CV rozpoczyna nową konwersję.",
        "Usuń kasuje profil trwale po drugim, potwierdzającym kliknięciu.",
      ],
      facts: ["Wiersze pokazują nazwisko kandydata (lub Kandydat bez nazwy), plik źródłowy, szablon i czas ostatniej zmiany."],
    },
    {
      id: "dashboard",
      title: "Dashboard",
      where: "Menu → Dashboard",
      purpose: "Zobacz, ile AI zużywa zespół i ile to kosztuje.",
      steps: [
        "Przetworzone raporty, tokeny (Łącznie, Średnio, Prompt, Cache, Odpowiedź) i Szacowany koszt z przełącznikiem USD / PLN.",
        "Zużycie według operacji rozbija koszt: analiza CV, przebiegi doświadczenia i edukacji, research firmy / uczelni / LinkedIn, konwersja, podsumowanie, akcje AI i tłumaczenie w Profile Builderze.",
      ],
      facts: ["Koszty są szacunkami na podstawie liczby tokenów. Dashboard obejmuje całe wdrożenie, nie tylko Twoje analizy."],
    },
    {
      id: "inbox",
      title: "Skrzynka feedbacku (tylko recenzenci i właściciele)",
      where: "Menu → Feedback (widoczne tylko z dostępem)",
      purpose: "Obsługuj feedback wysłany z raportów.",
      steps: [
        "Filtruj po statusie: Wszystkie, Nowy, W trakcie, Zaplanowany, Rozwiązany, Nie naprawiamy.",
        "Otwórz pozycję, aby zobaczyć ocenę, komentarz, autora i kontekst (Pokaż fragment CV, Pokaż sekcję raportu, Szczegóły błędu).",
        "Zmień status, dodaj Notatkę zespołu lub usuń pozycję (kliknij dwa razy).",
        "Zarządzaj dostępem (tylko właściciele): nadaj rolę Recenzent lub Właściciel po firmowym e-mailu albo cofnij dostęp.",
      ],
      facts: [
        "Recenzent: czyta i obsługuje feedback. Właściciel: dodatkowo zarządza dostępem, zbieraniem feedbacku i globalną retencją.",
        "Zawsze musi pozostać co najmniej jeden właściciel.",
      ],
    },
    {
      id: "settings",
      title: "Ustawienia",
      where: "Menu → Ustawienia",
      purpose: "Osobiste opcje wyświetlania oraz globalne kontrolki danych.",
      steps: [
        "Język interfejsu i Język analizy: English lub Polski, niezależnie.",
        "Research publiczny: włącz lub wyłącz research w sieci, podgląd ustaleń po najechaniu, rozwijanie sekcji domyślnie, automatyczny research per rodzaj.",
        "Retencja danych: ile dni przechowywane są ukończone analizy i zapisane CV (1 do 3650). Tylko właściciele; dotyczy każdego użytkownika.",
        "Usuń wszystkie analizy trwale kasuje każdą zapisaną analizę i CV w całym wdrożeniu. Potwierdź w oknie dialogowym.",
        "Stan systemu: Gotowe lub Wymaga uwagi, ze Szczegółami technicznymi per możliwość (baza danych, GeoNames, analiza, rodzaje researchu, Profile Builder, eksport PDF, feedback). Po awarii użyj Odśwież status.",
      ],
      facts: [
        "Język, podgląd i przełączniki researchu są zapisywane tylko w Twojej przeglądarce.",
        "Retencja i Usuń wszystkie dotyczą całego zespołu. Jeśli kontrolki są wyłączone, poproś właściciela feedbacku.",
      ],
    },
  ],
  boundariesTitle: "Czego aplikacja nie robi",
  boundaries: [
    "Nie weryfikuje tożsamości, uczciwości, miejsca zamieszkania, fizycznej lokalizacji, narodowości ani prawa do pracy. Informacja o UE i kontrole lokalizacji opisują tylko deklarowany adres.",
    "Nie ocenia punktowo, nie rankinguje i nie rekomenduje kandydatów. Ustalenia to pytania do zadania, nie werdykty.",
    "Nie wymyśla danych. Każda wartość profilu, zatrudnienia i edukacji wymaga dosłownego dowodu w CV.",
    "Nie wysyła treści CV do publicznego wyszukiwania. Researchowane są tylko zaakceptowane, poparte dowodami nazwy pracodawców, uczelni i kandydatów.",
    "Nie przechowuje plików bez końca. Analizy podlegają retencji, a Profile Builder nigdy nie zapisuje oryginalnego pliku CV.",
  ],
  glossaryTitle: "Słowniczek",
  glossary: [
    { term: "Dowód", meaning: "Dosłowny fragment CV, który potwierdza wartość lub ustalenie." },
    { term: "Wymaga uwagi", meaning: "Niespójność lub brak, który warto zweryfikować z kandydatem." },
    { term: "Warto wiedzieć", meaning: "Przydatny kontekst, który sam w sobie nie jest problemem." },
    { term: "Częściowy", meaning: "Raport, w którym co najmniej jedna sekcja nie została przeanalizowana pewnie." },
    { term: "Pewność", meaning: "Jak mocno źródła publiczne zgadzają się z CV: wysoka, średnia lub niska." },
    { term: "Anonimizacja", meaning: "Ukrycie wybranych pól w eksportowanym profilu bez zmiany zapisanych danych." },
    { term: "Retencja", meaning: "Liczba dni, przez które ukończone analizy i ich CV są przechowywane przed automatycznym usunięciem." },
    { term: "Właściciel / Recenzent", meaning: "Role feedbacku. Właściciele zarządzają też dostępem, retencją i zbieraniem feedbacku." },
  ],
};

export const manualContent: Record<AppLanguage, ManualContent> = { en, pl };

export const manualLabels: Record<AppLanguage, { quickStart: string; where: string; steps: string; facts: string; contents: string }> = {
  en: { quickStart: "Quick start", where: "Where", steps: "How to use it", facts: "Good to know", contents: "Contents" },
  pl: { quickStart: "Szybki start", where: "Gdzie", steps: "Jak używać", facts: "Warto wiedzieć", contents: "Spis treści" },
};
