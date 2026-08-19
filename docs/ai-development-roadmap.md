# Roadmapa rozwoju CV Analyzera

> Status: propozycja do konsultacji z szefem. Implementacja zaczyna się dopiero po akceptacji kierunku.

Pełne wymagania i zadania znajdują się w OpenSpec `add-ai-assisted-cv-analysis`.

## Kolejność prac

### Etap 0: prompt i test jakości

**Cel:** sprawdzić, czy GPT-5.6 Luna potrafi znaleźć użyteczne informacje na małej próbce CV.

Zakres:

- opracowanie wniosków z prywatnego folderu `data/`;
- taksonomia findingsów i lista rzeczy, których AI nie może oceniać;
- prompt i format odpowiedzi;
- cztery reprezentatywne CV;
- pomiar jakości, czasu i kosztu.

**Wynik:** powtarzalny test oraz zaakceptowany prompt. Bez zmian widocznych dla użytkownika.

### Vertical slice 1: użyteczny raport z jednego CV

**Cel:** przejść całą drogę od pliku do pierwszego raportu wspieranego przez AI.

Zakres:

- tekst z podziałem na strony;
- minimalny Markdown;
- jeden Document Analyzer bez internetu;
- evidence, importance i confidence;
- trzy grupy findingsów w UI;
- band nadal liczony przez kod.

**Wynik:** rekruter wrzuca jedno CV i dostaje użyteczny raport AI.

### Vertical slice 2: kolejka, workery i batch

**Cel:** obsłużyć wiele CV bez gubienia jobów i bez mieszania kontekstu kandydatów.

Zakres:

- trwała kolejka;
- worker skalowany przez Dockera;
- początkowo trzy równoległe joby;
- priorytet analizy CV nad researchem;
- bezpieczne przejmowanie i ponawianie jobów;
- osobne statusy plików;
- automatyczne odświeżanie raportów.

**Wynik:** batch może mieć dowolną liczbę CV, a gotowe raporty pojawiają się po kolei.

### Vertical slice 3: sprawdzanie firm

**Cel:** pozwolić rekruterowi sprawdzić firmy wskazane w CV.

Zakres:

- osobny przycisk w raporcie;
- OpenAI Web Search;
- daty, działalność, lokalizacja i relacja pracodawca-klient-projekt;
- źródła i neutralny brak danych;
- wynik bez wpływu na band.

**Wynik:** raport może zostać uzupełniony o sprawdzenie firm.

### Vertical slice 4: sprawdzanie edukacji i certyfikatów

**Cel:** sprawdzić uczelnie, programy, stopnie i certyfikaty.

Zakres:

- osobny przycisk i job;
- źródła, daty i informacje o programach;
- zagraniczna edukacja i brak danych pozostają neutralne.

**Wynik:** raport może zostać uzupełniony o sprawdzenie edukacji.

### Vertical slice 5: LinkedIn

**Cel:** znaleźć możliwy profil i porównać go z CV bez przypisywania złej osoby.

Zakres:

- wyszukiwanie możliwych profili;
- pokazanie powodów dopasowania;
- wybór profilu przez rekrutera;
- dopiero potem porównanie firm, ról, dat, lokalizacji i edukacji.

**Wynik:** rekruter może bezpiecznie potwierdzić profil i zobaczyć różnice względem CV.

### Vertical slice 6: cache i przygotowanie produkcyjne

**Cel:** ograniczyć koszty i sprawdzić zachowanie systemu przy dużych batchach.

Zakres:

- cache firm, uczelni i certyfikatów;
- testy dużych batchy;
- limity kosztów, wyszukiwań i czasu;
- monitoring i obsługa błędów;
- retencja i kontrola danych;
- pełniejszy test na korpusie Magdy;
- plan włączenia i wycofania funkcji.

**Wynik:** system jest gotowy do kontrolowanego uruchomienia produkcyjnego.

## Proponowane GitHub Issues

Po akceptacji roadmapy można utworzyć następujące issues:

1. `feat(ai): establish document analysis prompt and eval baseline`
2. `feat(ai): deliver AI-assisted single CV report`
3. `feat(jobs): add durable analysis queue and scalable workers`
4. `feat(research): add optional company research`
5. `feat(research): add education and certification research`
6. `feat(research): add LinkedIn discovery and consistency review`
7. `feat(ops): add research cache and production safeguards`

Każde issue odpowiada jednemu etapowi i może dostać osobny feature branch oraz osobną sesję implementacyjną.

## Rzeczy odłożone na później

- OCR dla skanowanych CV;
- obsługa Anthropic API;
- automatyczne uruchamianie wszystkich researchy;
- Tinderowe przeglądanie CV;
- rozbudowane funkcje batch review poza podstawową kolejką i raportami.
