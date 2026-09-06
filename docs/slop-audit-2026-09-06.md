# Slop audit, 2026-09-06

Punkt wyjścia: `refactor/repository-cleanup-2026-09-05`, commit `a26145a`.
Przed audytem wykonano `git fetch --all --prune`.

Audyt dotyczy zbędnego kodu, pozostałości usuniętej architektury, powielonej
logiki i granic odpowiedzialności. Nie ustala autorstwa kodu. Obejmuje
przegląd backendu, klienta researchu, wybranych komponentów i proxy web,
kontraktów feedbacku oraz konfiguracji repo. To nie jest pełny audyt
bezpieczeństwa ani wizualny przegląd UI.

## Poprawione

| Problem | Zmiana | Sprawdzenie |
| --- | --- | --- |
| Git przechowywał `apps/api/.venv` jako absolutny symlink do nieistniejącego worktree. Udokumentowana komenda testów nie działała w tym checkoutcie. | Usunięto symlink. W `.gitignore` wzorzec `.venv` obejmuje zarówno katalog, jak i symlink. | Weryfikacja celu linku; testy w osobnym środowisku. |
| `api/app.py` zawierał implementację blokad researchu i rejestru anulowania obok endpointów. | Wydzielono `api/concurrency.py`, zachowując algorytmy, klucze, limit wpisów i cykl życia instancji. | Testy izolacji właścicieli, limitu anulowań, współdzielenia blokady, niezależnych kluczy i zwolnienia po wyjątku; istniejący test anulowania przez HTTP. |
| Klient LinkedIn przekazywał stałe parametry do `_call`, który sprawdzał jedyny obsługiwany wariant. | Włączono wywołanie bezpośrednio do `discover`. Zachowano filtrowanie źródeł, normalizację confidence, limity, błędy i `store=False`. | Pięć nowych przypadków testowych przeszło przed i po uproszczeniu klienta. |
| Nieużywany `operations.timer()` i stałe `COMPARISON_VERSION`, `MAX_SEARCHES` w module LinkedIn sugerowały nieistniejących konsumentów. | Usunięto po sprawdzeniu odwołań. | Wyszukiwanie w kodzie i testach oraz pełny pytest. |
| Pierwsze zdanie architektury powtarzało nazwę strategii. | Korekta tekstu. | Przegląd diffu. |

## Kolejne zadania

Poniższe zadania są rozdzielone celowo. Nie zostały zaimplementowane w tym
diffie. Każde ma osobny zakres i warunek zakończenia; nie wymagają wspólnej
przebudowy aplikacji.

### 1. Usunąć generowanie feedbacku dla dawnych raportów, P2

`apps/api/src/cv_validator/api/feedback.py`, funkcje `_target_candidates`
i `_versions`, nadal odczytują `deterministic`, `document_understanding`,
`structural_audits`, `file_details`, `link_inspection` i `ai_analysis`.
To pozostałości kontraktów wycofanych w `docs/architecture.md`.
`tests/test_feedback.py` nadal testuje część funkcji na dawnych `findings`
i `ai_analysis`. Zielone testy nie potwierdzają tu zgodności z obecną architekturą.

- [ ] Zastąpić stare fixture'y przykładami `base-analysis-v2`, mechanicznych
  ustaleń i aktualnych wyników lub błędów researchu.
- [ ] Usunąć generowanie nowych targetów i wersji z usuniętych modułów.
- [ ] Zachować odczyt istniejącego feedbacku, triage i snapshotów. Nie usuwać
  historycznych rekordów ani migracji chroniącej feedback przed kaskadowym DELETE.
- [ ] Uaktualnić `openspec/specs/contextual-feedback/spec.md`, rozróżniając
  obecnie generowane targety od historycznych rodzajów przechowywanych w bazie.
- [ ] Sprawdzić stabilność identyfikatorów aktualnych targetów, zapis/wycofanie,
  błędy researchu oraz zachowanie feedbacku po delete, bulk delete i retention.

### 2. Wydzielić wykonanie researchu z fabryki FastAPI, P2

`api/app.py::research_subjects` nadal łączy dobór usługi, cache, blokady,
rozliczenie wywołań, zapis i tłumaczenie błędów HTTP. Samo rozdzielenie
plików endpointów nie rozwiąże tych zależności.

- [ ] Najpierw utrwalić testami cache hit/miss/refresh, równoległe żądania
  tego samego podmiotu, usunięcie raportu podczas wywołania i błędy zapisu.
- [ ] Przenieść wykonanie company/education research do jednej funkcji lub
  usługi z jawnymi zależnościami. Zostawić auth, nagłówki i HTTP w API.
- [ ] Zachować kontekst edukacji zależny od właściciela poza wspólnym cache,
  deduplikację kosztów i aktualną kolejność zapisów. Sprawdzić ledger kosztów.

### 3. Ujednolicić proxy company/education research, P3

Pliki `apps/web/src/app/api/analyses/[analysisId]/research/company/route.ts`
i `education/route.ts` powielają uwierzytelnienie, walidację flag, nagłówki
i przekazanie odpowiedzi. Różnią się adresem usługi i formatowaniem.

- [ ] Dodać testy zachowania proxy: brak sesji, brak tokena, wyłączone AI,
  refresh, kodowanie ID, odpowiedź upstream bez JSON i status błędu.
- [ ] Wydzielić mały wspólny handler z zamkniętą listą kategorii. Nie budować
  ogólnego frameworka proxy ani zmieniać sposobu autoryzacji.

### 4. Współdzielić powiadomienie o wyniku automatycznego researchu, P3

Panele `company-research.tsx`, `education-research.tsx` i
`linkedin-research.tsx` powielają ref ostatniego wyniku, ref callbacku i dwa
efekty powiadamiające o zakończeniu. Różne widoki wyników pozostają uzasadnione.

- [ ] Sprawdzić remount, zmianę analysis ID i callbacku, zakończenie manualnego
  researchu oraz brak powtórnego powiadomienia dla tej samej referencji wyniku.
- [ ] Wydzielić wyłącznie mechanizm powiadomienia do wspólnego hooka.
  Zachować niezależne renderowanie i obecny orchestrator.

## Elementy pozostawione świadomie

`AnalysisStrategy` ma jedną produkcyjną implementację, ale wyznacza kontrakt
pipeline'u i umożliwia testy bez wywołań modelu. Nie jest martwą fabryką.
Walidacja literalnych dowodów, relacji i tożsamości raportu chroni różne
granice. Nie usuwano jej jako pozornego dublowania walidacji.

Vulture nie wykazał potwierdzonego martwego kodu przy progu 80%. Wskazania
dotyczyły argumentów protokołu `__exit__`. Niższy próg wskazywał także
endpointy, walidatory Pydantic, interfejsy Docling i metody odczytu audytu
używane w testach. Nie usuwano ich na podstawie samego skanera.

## Weryfikacja

- Niezmieniony branch, pełna kopia repo: **200 testów backendu przeszło**.
- Po poprawkach: **208 testów backendu przeszło**, bez zmian istniejących testów.
- Frontend na Node **22.23.2**: **12 plików testowych przeszło**, typecheck
  i produkcyjny build Next.js przeszły.
- ESLint: zero błędów, dwa zastane ostrzeżenia `no-img-element` w
  `app-sidebar.tsx` i `login-07.tsx`.
- `git diff --check`: bez błędów.

Backend testowano przez `/tmp/cv-slop-audit-venv/bin/pytest`, z zależnościami
z `apps/api/pyproject.toml`. Frontend zainstalowano z zamrożonego lockfile.
TestClient blokował się w sandboxie także przed poprawkami; poza nim testy
przeszły. Build wymagał dostępu do Google Fonts. Nie zmieniano kodu aplikacji
ani konfiguracji zależności w celu obejścia tych ograniczeń środowiska.

Nie uruchamiano stosu Docker, przeglądarki ani płatnych wywołań modeli.
Wyniki testów nie stanowią gwarancji braku regresji w tych ścieżkach.
