# Proponowany pipeline AI

> Szkic do rozmowy z szefem. To jeszcze nie jest plan wdrożenia.

## Cel

Rekruter ma szybko dostać użyteczny raport z CV. Dodatkowe sprawdzanie w
internecie uruchamia tylko wtedy, gdy go potrzebuje.

AI pomaga znaleźć informacje i niespójności, ale nie podejmuje decyzji o
kandydacie i nie potwierdza jego tożsamości ani miejsca pobytu.

## Jak ma to działać

```text
CV lub batch CV
  -> pdfplumber wyciąga tekst
  -> OpenAI analizuje jedno CV
  -> powstaje podstawowy raport
  -> rekruter może uruchomić dodatkowe sprawdzanie
  -> nowe wyniki pojawiają się później w tym samym raporcie
```

### Analiza CV

- Zostajemy przy `pdfplumber` i obecnej obsłudze DOCX.
- Zachowujemy podział na strony i tekst bez zbędnych zmian.
- OpenAI dostaje prosty Markdown z granicami stron, bez zgadywania nagłówków,
  tabel i kolumn.
- Jedno CV oznacza jedno niezależne wywołanie OpenAI, bez dostępu do internetu.
- Model szuka faktów, niespójności, braków i rzeczy, które warto sprawdzić.
- Każdy finding wskazuje stronę, fragment CV, wagę i poziom pewności.
- Gdy danych brakuje, model zwraca `unknown` zamiast zgadywać.
- Końcowy band nadal wylicza kod.

Jeśli plik nie ma wystarczającej ilości tekstu, pokazujemy prosty komunikat i
kończymy analizę.

Folder `data/` służy tylko do pracy nad promptem i testami. Nie trafia do repo
ani do działającej aplikacji.

### Raport podstawowy

Raport pojawia się po analizie CV. Wyniki dzielimy na:

- Wymaga uwagi
- Warto wiedzieć
- Pozostałe sygnały, domyślnie zwinięte

Waga findingu i pewność modelu są osobnymi wartościami. Finding bez dowodu nie
może być pokazany jako fakt.

### Dodatkowe sprawdzanie

Rekruter może osobno uruchomić:

- sprawdzenie firm;
- sprawdzenie wykształcenia i certyfikatów;
- wyszukanie potencjalnego profilu LinkedIn.

`ResearchJobScheduler` jest zwykłą warstwą kodu. Sprawdza wybór użytkownika,
cache i dane z CV, po czym dodaje potrzebne joby do kolejki.

Do researchu używamy tylko OpenAI Web Search. Każdy wynik ma źródło i poziom
pewności. Brak znalezionej firmy, uczelni lub profilu nie jest problemem.
Potencjalny profil LinkedIn musi potwierdzić rekruter. Research nie zmienia
automatycznie bandu.

### Kolejka i workery

- Kolejka może przyjąć dowolną liczbę CV.
- Docker uruchamia ustaloną liczbę workerów. Na początek planujemy trzy.
- Analiza CV ma wyższy priorytet niż research.
- Każdy job zaczyna z pustym kontekstem.
- Jeden job może być wykonywany tylko przez jednego workera.
- Jeśli worker padnie, job wraca do kolejki.
- Ponowne wykonanie joba nie może dodać tych samych wyników drugi raz.
- Frontend sam odświeża raport i pokazuje stan każdego joba.

Możemy ponownie wykorzystywać aktualne wyniki dotyczące tej samej firmy,
uczelni lub certyfikatu. Dane LinkedIna pozostają przypisane do konkretnego
kandydata.

## Ustalone na teraz

- Korzystamy tylko z OpenAI.
- Podstawowa analiza używa AI, ale nie internetu.
- Research jest opcjonalny i działa w tle.
- Użytkownik wybiera, co chce sprawdzić.
- Jobami zarządza kod, a nie kolejny agent AI.
- Workery mają wspólną kolejkę i limit ustawiany w konfiguracji.
- Każdy job ma osobny kontekst.
- Oryginalny plik CV usuwamy po analizie.
- Na razie raport i dowody przechowujemy przez 90 dni.
- Oficjalnie wspieramy CV po polsku i angielsku.

## Do ustalenia podczas wdrożenia

- Jakiej kolejki i biblioteki do workerów użyjemy.
- Czy i kiedy zmienimy SQLite na inną bazę.
- Ile jobów może działać równocześnie.
- Jak długo job może działać i ile razy go ponawiamy.
- Jak długo trzymamy cache.
- Ostateczny prompt, format odpowiedzi i ustawienia modelu.
- Limity kosztów i liczby wyszukiwań.
- Monitoring i docelowy czas przechowywania danych.
