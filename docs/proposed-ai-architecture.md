# Pipeline AI w obecnej architekturze

> Kierunek po decyzji CTO: dodajemy funkcje Magdy bez nowych usług, kolejki i workerów.

## Cel

Rekruter przesyła CV i po zakończeniu requestu dostaje raport wspierany przez AI. Dodatkowe sprawdzanie w internecie uruchamia osobno, gdy go potrzebuje.

AI pomaga znaleźć informacje i niespójności, ale nie podejmuje decyzji o kandydacie i nie potwierdza jego tożsamości ani miejsca pobytu.

## Jak ma to działać

```text
Next.js
  -> istniejące FastAPI
  -> pdfplumber lub python-docx
  -> reguły deterministyczne + OpenAI Document Analyzer
  -> jeden wspólny Report
  -> SQLite
  -> odpowiedź JSON i widok HTML
```

Nie dodajemy nowego kontenera ani usługi. OpenAI Document Analyzer jest modułem wywoływanym przez obecny `pipeline.py`.

## Analiza CV

- Zostajemy przy `pdfplumber` i obecnej obsłudze DOCX.
- Zachowujemy podział na strony i tekst bez zbędnych zmian.
- OpenAI dostaje prosty Markdown z granicami stron.
- Jedno CV oznacza jedno niezależne wywołanie OpenAI bez dostępu do internetu.
- Model zwraca ustrukturyzowane dane kontaktowe, edukację i historię zatrudnienia.
- Model szuka faktów, niespójności, braków i rzeczy, które warto sprawdzić.
- Każdy finding wskazuje stronę, fragment CV, wagę i poziom pewności.
- Kod dodaje wymagane flagi numeru telefonu, miasta i zbiorczej lokalizacji poza UE.
- Gdy danych brakuje, wynik pokazuje brak lub niepewność zamiast zgadywać.
- Końcowy band nadal wylicza kod.

Jeśli plik nie ma wystarczającej ilości tekstu, pokazujemy prosty komunikat i kończymy analizę.

Folder `data/` służy tylko do pracy nad promptem i testami. Nie trafia do repo ani do działającej aplikacji.

## Raport podstawowy

API zwraca raport dopiero po zakończeniu reguł i analizy AI. Wyniki dzielimy na:

- Wymaga uwagi;
- Warto wiedzieć;
- Pozostałe sygnały, domyślnie zwinięte.

Raport zawiera pełną checklistę flag z kart Magdy. Ten sam model danych jest dostępny jako JSON i czytelny widok HTML. Finding bez dowodu nie może być pokazany jako pewny fakt.

## Dodatkowe sprawdzanie

Po zapisaniu raportu rekruter może osobno uruchomić:

- sprawdzenie firm;
- sprawdzenie wykształcenia i certyfikatów;
- wyszukanie potencjalnego profilu LinkedIn.

Każdy przycisk wykonuje zwykły request do istniejącego FastAPI:

```text
przycisk w raporcie
  -> endpoint researchu
  -> sprawdzenie danych i cache w SQLite
  -> OpenAI Web Search
  -> walidacja odpowiedzi
  -> zapis wyniku w SQLite
  -> odpowiedź i aktualizacja raportu
```

Frontend pokazuje loading do końca requestu. Jeśli request się nie uda, raport pozostaje dostępny, a użytkownik może spróbować ponownie.

Pokazujemy wszystkie wymagane przez Magdę sygnały: ograniczoną obecność firmy online, nietypową lokalizację uczelni, brak znalezionego LinkedIna oraz widoczność zdjęcia i liczby kontaktów na możliwym profilu. Każdy wynik zawiera źródła, poziom pewności i ograniczenia wyszukiwania.

Potencjalny profil LinkedIn musi potwierdzić rekruter. Research nie zmienia automatycznie bandu.

## Batch w V1

Obecny endpoint batch analizuje CV po kolei w jednym requeście. Dodanie AI wydłuży czas proporcjonalnie do liczby plików.

Dlatego przed włączeniem funkcji:

- mierzymy czas jednego CV i kilku realistycznych batchy;
- ustawiamy maksymalną liczbę plików i rozmiar requestu;
- pokazujemy użytkownikowi, że analiza może potrwać;
- nie obiecujemy batchy dowolnej wielkości.

Jeśli pomiary pokażą, że wymagany wolumen nie mieści się w requestach HTTP, przygotujemy osobny plan kolejki i workerów do zatwierdzenia.

## Ustalone na teraz

- Korzystamy tylko z OpenAI.
- Zostajemy przy obecnych usługach `web` i `api`.
- Zostajemy przy SQLite.
- Podstawowa analiza działa synchronicznie i nie używa internetu.
- Research jest opcjonalny, synchroniczny i uruchamiany przez użytkownika.
- Każde wywołanie modelu ma osobny kontekst.
- Wszystkie karty Magdy należą do wymaganego zakresu produktu.
- Oryginalny plik CV usuwamy po analizie.
- Na razie raport i dowody przechowujemy przez 90 dni.
- Oficjalnie wspieramy CV po polsku i angielsku.

## Do ustalenia podczas wdrożenia

- Ostateczny prompt, format odpowiedzi i ustawienia modelu.
- Timeout analizy dokumentu i każdego researchu.
- Maksymalna liczba CV w synchronicznym batchu.
- Limity kosztów i liczby wyszukiwań.
- Czas ważności cache w SQLite.
- Próg kompletności profilu LinkedIn.
- Definicja małej lub nietypowej miejscowości poza UE.
- Monitoring i docelowy czas przechowywania danych.

## Poza tym planem

Kolejka, workery, lease'y, polling, automatyczne wznawianie i migracja bazy nie są częścią V1. Wrócimy do nich tylko z pomiarami pokazującymi konkretny problem.
