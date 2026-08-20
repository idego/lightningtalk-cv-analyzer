# Roadmapa rozwoju CV Analyzera

> Status: propozycja po decyzji CTO. Dodajemy funkcje do architektury istniejącej w repo. Kolejka, osobne workery i migracja bazy nie należą do V1.

Pełne wymagania i zadania znajdują się w OpenSpec `add-ai-assisted-cv-analysis`.

## Zakres biznesowy z kart Magdy

Wszystkie poniższe elementy należą do zakresu produktu:

- ekstrakcja danych kontaktowych: numeru telefonu oraz miasta lub adresu;
- ekstrakcja uczelni, kierunku i lat nauki;
- ekstrakcja firm, stanowisk i okresów zatrudnienia;
- flaga numeru telefonu z kraju spoza UE;
- sprawdzenie istnienia, kraju i nietypowości podanej miejscowości;
- zbiorcza flaga lokalizacji poza UE;
- wyszukiwanie możliwego profilu LinkedIn;
- ocena widoczności zdjęcia i sensownej liczby kontaktów na profilu;
- flaga braku znalezionego profilu LinkedIn;
- sprawdzenie istnienia uczelni;
- sprawdzenie miasta i kraju uczelni względem reszty CV;
- sprawdzenie istnienia firm;
- flaga firmy bez wykrywalnej obecności online;
- zbiorcza checklista flag z uzasadnieniami;
- czytelny wynik per kandydat w JSON i HTML.

GitHub Issues rozbiją te wymagania na szczegóły techniczne. OpenSpec opisuje ich wspólne zasady i kolejność wdrożenia.

## Ograniczenia V1

- Zostajemy przy Next.js, FastAPI, Pythonie, SQLite i obecnym Docker Compose.
- Analiza AI działa w tym samym requeście co obecna analiza CV.
- Research działa w osobnym, synchronicznym requeście po kliknięciu użytkownika.
- Obecny batch analizuje pliki po kolei i dostanie zmierzony limit wielkości.
- Jeśli request zostanie przerwany, niezakończona praca nie jest wznawiana automatycznie.
- Nie obiecujemy dowolnie dużych batchy ani pracy w tle.

## Kolejność prac

### Etap 0: prompt i test jakości

**Cel:** sprawdzić, czy GPT-5.6 Luna znajduje użyteczne informacje na małej próbce CV.

Zakres:

- opracowanie anonimowych wniosków z prywatnego folderu `data/`;
- mapowanie wszystkich kart Magdy na prompt, regułę, research, UI albo test;
- prompt i format odpowiedzi;
- cztery reprezentatywne CV;
- pomiar jakości, czasu i kosztu.

**Wynik:** powtarzalny test oraz zaakceptowany prompt. Bez zmian widocznych dla użytkownika.

### Vertical slice 1: synchroniczny raport AI z jednego CV

**Cel:** dodać AI do istniejącego pipeline'u bez zmiany usług i sposobu wdrożenia.

Zakres:

- tekst z podziałem na strony i minimalny Markdown;
- jeden Document Analyzer bez internetu;
- ustrukturyzowane dane kontaktowe, edukacja i historia zatrudnienia;
- flagi numeru telefonu, miasta i zbiorczej lokalizacji poza UE;
- dowody, importance i confidence;
- pełna checklista flag oraz wynik JSON/HTML;
- trzy grupy findingsów w UI;
- band nadal liczony przez kod;
- pomiar czasu jednego CV i obecnego batcha.

**Wynik:** rekruter czeka na jeden request i dostaje kompletny raport AI. Ustalamy praktyczny limit batcha.

### Vertical slice 2: synchroniczne sprawdzanie firm

**Cel:** pozwolić rekruterowi sprawdzić firmy wskazane w zapisanym raporcie.

Zakres:

- osobny przycisk i endpoint w istniejącym API;
- OpenAI Web Search;
- daty, działalność, lokalizacja i relacja pracodawca-klient-projekt;
- sprawdzenie strony, publicznych profili firmy i dostępnych rejestrów;
- widoczna flaga ograniczonej obecności firmy online;
- źródła, ograniczenia i retry po błędzie;
- wynik bez wpływu na band.

**Wynik:** po zakończeniu requestu raport pokazuje sprawdzenie firm.

### Vertical slice 3: synchroniczne sprawdzanie edukacji i certyfikatów

**Cel:** sprawdzić uczelnie, programy, stopnie i certyfikaty.

Zakres:

- osobny przycisk i endpoint;
- źródła, daty i informacje o programach;
- miasto i kraj uczelni oraz różnice względem reszty CV;
- retry po błędzie;
- wynik bez wpływu na band.

**Wynik:** po zakończeniu requestu raport pokazuje sprawdzenie edukacji.

### Vertical slice 4: synchroniczne sprawdzanie LinkedIna

**Cel:** znaleźć możliwy profil i porównać go z CV bez przypisywania złej osoby.

Zakres:

- osobny przycisk i endpoint;
- wyszukiwanie możliwych profili;
- powody dopasowania;
- informacja o widoczności zdjęcia i liczby kontaktów;
- widoczna flaga braku znalezionego profilu wraz z ograniczeniami wyszukiwania;
- wybór profilu przez rekrutera;
- dopiero potem porównanie firm, ról, dat, lokalizacji i edukacji.

**Wynik:** po zakończeniu requestu rekruter widzi kandydatów na profil i może potwierdzić właściwy.

### Vertical slice 5: utwardzenie V1 w obecnej architekturze

**Cel:** ograniczyć koszty i ustalić realne granice obecnego rozwiązania.

Zakres:

- cache firm, uczelni i certyfikatów w SQLite;
- testy realistycznych batchy;
- limity liczby plików, czasu, kosztów i wyszukiwań;
- monitoring requestów i obsługa błędów;
- retencja i kontrola danych;
- pełniejszy test na korpusie Magdy;
- plan włączenia i wycofania funkcji.

**Wynik:** znamy użyteczny zakres V1. Jeśli pomiary pokażą potrzebę pracy w tle, przygotowujemy osobną propozycję architektoniczną.

## Proponowane GitHub Issues

Po akceptacji roadmapy można utworzyć następujące issues:

1. `feat(ai): establish document analysis prompt and eval baseline`
2. `feat(ai): add synchronous AI-assisted CV report`
3. `feat(research): add synchronous company research`
4. `feat(research): add synchronous education research`
5. `feat(research): add synchronous LinkedIn review`
6. `feat(ops): measure and harden synchronous AI workflow`

Każde issue odpowiada jednemu etapowi i może dostać osobny feature branch oraz osobną sesję implementacyjną.

## Poza V1

- trwała kolejka i background jobs;
- osobne workery i skalowanie przez Docker;
- automatyczne wznawianie przerwanych analiz;
- automatyczne pojawianie się wyników po zakończeniu requestu;
- migracja z SQLite wymuszona skalą;
- dowolnie duże batche;
- OCR dla skanowanych CV;
- obsługa Anthropic API;
- automatyczne uruchamianie wszystkich researchy;
- Tinderowe przeglądanie CV.
