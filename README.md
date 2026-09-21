# KKS Basket Poznań Lab

Ekstraktor statystyk koszykarskich + statyczny portal analityczny dla
KKS Basket Poznań (Enea Basket Poznań) w PZKosz 1 Lidze Mężczyzn.

**Portal na żywo: https://aliksix.github.io/basket_lab/**

Projekt ma dwie części:

| Katalog | Co robi |
| --- | --- |
| `extractor/` | pobiera i przelicza dane (Python 3.11+, zero zależności zewnętrznych) |
| `docs/` | portal publikowany przez GitHub Pages (czysty HTML/CSS/JS, bez build stepu) |

---

## 1. Ekstraktor

### Źródła danych

**FIBA LiveStats (Genius Sports)** — źródło podstawowe. Strona meczu
`https://fibalivestats.dcd.shared.geniussports.com/u/POL/<matchId>/index.html`
czyta dane z publicznego endpointu:

```
https://fibalivestats.dcd.shared.geniussports.com/data/<matchId>/data.json
```

W jednym pliku są: boxscore drużyn i zawodników, pełne play-by-play (łącznie ze
zmianami z dokładnym czasem) oraz **współrzędne wszystkich rzutów z gry**.
To ostatnie pozwala rysować mapy rzutów i liczyć strefy.

**PZKosz (`1lm.pzkosz.pl`)** — terminarz, wyniki, daty, hale, numery kolejek
oraz zapasowe play-by-play renderowane w HTML (bez współrzędnych rzutów).
Używane, gdy mecz nie był obsługiwany przez LiveStats.

### Instalacja

```bash
cd extractor
python -m basketlab --help
```

Wymagany jest sam Python 3.11+ — biblioteka korzysta wyłącznie ze standardowej
biblioteki (`urllib`, `json`, `re`, `concurrent.futures`).

### Polecenia

```bash
# cały mecz (boxscore + pbp + rzuty) w jednolitym JSON-ie
python -m basketlab game https://fibalivestats.dcd.shared.geniussports.com/u/POL/2905346/index.html --out mecz.json

# surowy data.json prosto z Genius Sports
python -m basketlab game 2905346 --raw --out ../data/raw/2905346.json

# samo play-by-play - z LiveStats albo ze strony PZKosz
python -m basketlab pbp 2905346 --csv pbp.csv
python -m basketlab pbp https://1lm.pzkosz.pl/mecz/223889/gks-tychy---pge-spojnia-stargard.html --csv pbp.csv

# mapa rzutów jednego meczu (x, y, strefa, dystans, kąt)
python -m basketlab shots 2905346 --out rzuty.json

# terminarz i wyniki (bieżący sezon albo archiwum)
python -m basketlab schedule --out terminarz.json
python -m basketlab schedule --seasons          # lista dostępnych sezonów
python -m basketlab schedule --archive 28       # sezon 2025/2026

# mapowanie terminarz PZKosz -> identyfikatory LiveStats
python -m basketlab discover --step 1 --range 2902000-2908000

# kontrola poprawności rejestru (pełne pobranie każdego meczu)
python -m basketlab verify

# komplet danych dla portalu -> docs/data + docs/assets
python -m basketlab build

# portrety zawodnikow z PZKosz (wymaga Pillow, raz na sezon)
python -m basketlab photos
```

### Rejestr meczów

Genius Sports nie udostępnia publicznego indeksu rozgrywek: `data.json`
pojawia się dopiero dla rozegranego meczu, a identyfikatory są globalne dla
wszystkich klientów LiveStats na świecie. Mapowanie „mecz z terminarza →
identyfikator LiveStats" budujemy więc raz i trzymamy w
`data/registry/1lm-2026-2027.json`.

`discover` działa trzystopniowo:

1. **skan** zadanego zakresu identyfikatorów,
2. **zagęszczenie** wokół trafień (mecze jednej kolejki leżą obok siebie),
3. **predykcja** — interpolacja *data → identyfikator* na podstawie już
   dopasowanych meczów i skan wąskiego okna wokół przewidywanej wartości.

Każde trafienie jest potwierdzane pełnym pobraniem meczu (zgadza się nazwa
i wynik obu drużyn), bo sam nagłówek `data.json` zawiera tylko gospodarzy.
Fixture'y jednego sezonu PZKosz leżą w jednym, wąskim bloku — dla sezonu
2026/2027 wystarczy zakres `2902000-2908000` przeskanowany z krokiem 1.

Mecz, którego identyfikator znasz, można dopisać ręcznie:

```bash
python -m basketlab add 2905346 --pzkosz-id 223891 --date 2026-09-19 --round 1
```

### Co liczy ekstraktor

* **Posiadania z play-by-play** — posiadanie to maksymalny ciąg zdarzeń jednej
  drużyny; zbiórka w ataku go nie kończy, rzuty wolne po faulu przy celnym
  rzucie należą do tego samego posiadania.
* **Składy na parkiecie** — odtwarzane ze zdarzeń `substitution` (pierwsza
  piątka z boxscore + każde wejście/zejście), co daje piątki, duety, on/off
  i pojedynki piątka kontra piątka.
* **Strefy rzutowe** — dwie siatki liczone z geometrii boiska **FIBA**
  (28 × 15 m, pole 4.9 × 5.8 m, obręcz 1.575 m od linii końcowej, łuk 6.75,
  narożnik 6.60 w odległości 0.90 m od linii bocznej):
  zbiorcza `RIM / PAINT / SHORT_MID / LONG_MID / CORNER_3 / ABOVE_BREAK_3`
  do tabel oraz szczegółowa (14 stref z podziałem na sektory kątowe:
  `RA, PAINT, SM_L/R, LM_L/LC/C/RC/R, C3_L/R, AB3_L/C/R`) do mapy rzutów.
  Obie są spójne: każda strefa szczegółowa należy do dokładnie jednej zbiorczej
  (pilnuje tego test).
* **Ratingi skorygowane** — iteracyjna korekta ORTG/DRTG o siłę rywala
  (odpowiednik AdjO/AdjD z KenPom) wraz z SOS i przewagą własnej hali.
* **Impact zawodnika** — skorygowane on/off zmieszane z modelem box-score.
  Model nie jest przepisany z innej ligi: współczynniki dopasowuje regresja
  grzbietowa do skorygowanego on/off tej konkretnej ligi, więc opisuje 1 LM.
  Dzięki liniowości modelu ten sam zestaw współczynników daje rozbicie wpływu
  na rzuty, kreowanie, straty, zbiórki i obronę.
* **xPTS lite** — oczekiwane punkty na rzut przy ligowej skuteczności w danych
  strefach; różnica względem rzeczywistego PPS to *shot making*.
* **Kill shots** — serie co najmniej 10 punktów bez odpowiedzi rywala.
* **Clutch time** — ostatnie 5 minut IV kwarty i cała dogrywka przy różnicy
  punktowej do 5. Przynależność sprawdzana jest **na początku każdego
  posiadania**, więc mecz wchodzi i wychodzi z clutch time w trakcie końcówki.
  Liczone osobno dla zawodników (box score + on/off) i dla piątek.
* **Akcje „+15"** — posiadania, w których pierwsza szansa trwała co najmniej
  15 sekund, czyli gra przeciwko ustawionej obronie. Rzuty i punkty po własnej
  zbiórce w ataku są pomijane, bo sztucznie wydłużałyby akcję. Stąd dwa
  wskaźniki: **%FGA +15** (odsetek rzutów z długich akcji) i **PPP +15**
  (punkty na jedno długie posiadanie).

### Portrety zawodników

LiveStats podaje zdjęcia 200 × 200 z szerokim szarym tłem dookoła sylwetki.
PZKosz trzyma te same sesje w wyższej rozdzielczości:

```
https://s1.static.esor.pzkosz.pl/internalfiles/image/zawodnicy
    /s<sezon>/<klub>/600-600/<zawodnik>.jpg      # realnie 496 × 600
```

`basketlab photos` pobiera je i przycina, tworząc **dwa warianty na zawodnika**:

| Plik | Format | Gdzie |
| --- | --- | --- |
| `<klucz>.webp` | 316 × 380 (proporcje 158 × 190) | karty zawodników, nagłówek profilu |
| `<klucz>-icon.webp` | 192 × 192, ciasno na głowę | koła w tabelach, przy piątkach i duetach |

Tło usuwa **wypełnienie od krawędzi kadru**, a nie próg koloru — próg zjadłby
białe wykończenie koszulki i jasne logo, bo mają zbliżoną jasność do tła.
Linię ramion wykrywa skok szerokości kolejnych wierszy maski, dzięki czemu kadr
ikony trafia w głowę bez rozpoznawania twarzy.

Wysokość kadru liczona jest **w wysokościach głowy** (1.75 dla portretu, 1.25
dla ikony), a nie w pikselach źródła — dzięki temu wszyscy zawodnicy mają tę
samą skalę twarzy niezależnie od tego, jak ciasno ustawiono aparat na sesji.
Kadr jest wypalony w pliku, więc portal nie skaluje ani nie przesuwa niczego
w CSS — wystarczy `object-fit: cover`. Identyfikatory sezonu, klubu i zawodnika
czytane są ze strony zawodnika, więc nic nie jest zaszyte w kodzie.

Moduł jest jedynym miejscem wymagającym **Pillow**; reszta pakietu nie ma
żadnych zależności zewnętrznych, dlatego zdjęcia przetwarza się osobnym
poleceniem, a nie przy każdym `build`. Bez Pillow `build` działa normalnie
i używa zdjęć z LiveStats.

### Struktura pakietu

```
extractor/basketlab/
  http.py         klient HTTP z cache na dysku
  model.py        wspólny model meczu (Game / Team / Player / Event / Shot)
  court.py        geometria boiska FIBA i klasyfikacja stref
  fiba.py         parser data.json z LiveStats
  pzkosz.py       parser terminarza i HTML-owego play-by-play
  discover.py     rejestr meczów i wyszukiwanie identyfikatorów
  possessions.py  posiadania, składy, stinty
  metrics.py      metryki pochodne (Four Factors, USG%, TS%, ...)
  impact.py       ratingi skorygowane i model wpływu zawodnika
  linalg.py       regresja grzbietowa bez zależności zewnętrznych
  season.py       agregacja sezonu
  build.py        przeliczenie danych portalu
  site.py         zapis JSON-ów i zasobów do docs/
  photos.py       portrety z PZKosz: wycięcie tła i kadrowanie (Pillow)
  glossary.py     słownik metryk (treść dymków)
  cli.py          interfejs wiersza poleceń
```

---

## 2. Portal

Statyczna strona w `docs/`, publikowana przez GitHub Pages. Jasny interfejs
roboczy z granatową belką nawigacyjną w barwach klubu (granat `#1B1E45`,
błękit `#3A5BD9`). Motyw jasny i ciemny przełącznikiem w prawym górnym rogu.

| Strona | Zawartość |
| --- | --- |
| `index.html` | panel drużyny: OFF/DEF/NET RTG, tempo, ratingi skorygowane, Four Factors, profil rzutowy, forma mecz po meczu, tabela ligi, mapa stylu |
| `players.html` | kafle zawodników w układzie Dunks & Threes: Impact z miejscem w lidze, linie OFF/DEF, dwa PPP, wykres pizza sześciu umiejętności |
| `player.html?p=…` | profil: rozbicie wpływu, percentyle, on/off, Shooting Lab (mapa rzutów + strefy + xPTS), mecz po meczu |
| `games.html?m=…` | pełne play-by-play meczu, filtr po zawodniku i kwarcie, posiadania |
| `lineups.html` | piątki z miniaturami zdjęć, tabela piątek, tabela duetów z synergią |
| `lineup.html?l=…` | piątka: Four Factors, mecz po meczu, pojedynki z piątkami rywali |
| `league.html` | cała liga: ratingi, Four Factors, profil rzutowy, mapa stylu |
| `scout.html?t=…` | skauting rywala: profil gry, mocne i słabe strony, kluczowi zawodnicy, najczęstsze piątki |

Każda metryka ma znak `?` z wyjaśnieniem po polsku (`docs/data/glossary.json`,
źródło: `extractor/basketlab/glossary.py`).

### Mapa rzutów

Cztery tryby przełączane jednym kliknięciem:

| Tryb | Co pokazuje |
| --- | --- |
| **Rzuty** | pojedyncze znaczniki — kółko = trafiony, krzyżyk = niecelny |
| **Strefy** | 14 stref z podpisem `trafione/oddane` i skutecznością, w skali czerwony–zielony |
| **Hex** | kafelki heksagonalne: wielkość = liczba prób, kolor = PPS ponad oczekiwany |
| **Oba** | strefy wyciszone jako tło pod znacznikami |

Kolor strefy to PPS na tle ligi w tej samej strefie, **wytłumiony przy małej
próbie** (`n / (n + 8)`) — jedna trafiona trójka nie zabarwia całego sektora na
intensywną zieleń. Kafelki hex porównują się do oczekiwanego PPS wynikającego
z tego, skąd padły rzuty, więc kolor mówi o trafianiu, a nie o doborze pozycji.

### Karta zawodnika

Układ przeniesiony z Dunks & Threes:

```
IMPACT  0.0   #42 z 82
OFF  ──────●────   +0.1  #27
DEF  ────●──────   −0.1  #53
19.0 PKT · 1.20 PPP · 1.31 PPP ON
        ◔ wykres pizza: PTS 88 · TS% 65 · AST 73
          TOV 62 · STL 69 · BLK 42
```

Ocena główna z **miejscem w lidze** (nie percentylem). Pod nią OFF i DEF jako
**linie** — tor od najgorszego do najlepszego w lidze ze znacznikiem w miejscu
zawodnika. Na dole **wykres pizza**: sześć kawałków o równym kącie, gdzie
zmienną jest promień, czyli percentyl w lidze. Kategorie i ich kolejność są te
same co na D&T (PTS, TS%, AST, TOV, STL, BLK).

TOV jest odwrócone przy liczeniu percentyla, więc długi kawałek zawsze znaczy
„dobrze" — inaczej gracz z najniższą stratowalnością wyglądałby najgorzej.
Surowa wartość i miejsce w lidze trafiają do dymka.

Dwa różne PPP, celowo pokazywane obok siebie:

| | Co liczy |
| --- | --- |
| **PPP** | `PTS / (FGA + 0.44 × FTA + TOV)` — punkty na posiadanie zakończone akcją tego zawodnika |
| **PPP ON** | punkty zespołu na posiadanie, gdy zawodnik jest na parkiecie (czyli ORTG on / 100) |

Pierwsze mówi o jego własnej efektywności, drugie o tym, jak radzi sobie cały
atak przy nim — to nie to samo i rozjazd między nimi bywa najciekawszy.

### Rywale i skauting

Dane obejmują **całą ligę**, nie tylko klub:

- `players.html` i `lineups.html` mają wybór drużyny — można podejrzeć kadrę
  i piątki dowolnego rywala (dla rywali zbieramy tylko najczęściej grające
  piątki, duety liczymy wyłącznie dla własnej drużyny),
- profil zawodnika (`player.html`) istnieje dla każdego gracza w bazie,
- `scout.html` otwiera domyślnie **najbliższego rywala z terminarza** i składa
  jego profil: ratingi z miejscami w lidze, Four Factors po obu stronach,
  mapa stref, kluczowi zawodnicy i najczęstsze piątki.

Sekcja „Analiza gry" wylicza mocne i słabe strony z miejsc drużyny w tabelach
ligowych: trzy najwyższe pozycje trafiają do „na co uważać", trzy najniższe do
„gdzie szukać przewagi". Cechy opisujące wyłącznie styl (tempo, udział trójek)
są oznaczone osobno — wysokie tempo nie jest ani zaletą, ani wadą.

### Mapa stylu

Wykres porównujący zespoły ma **wybór wskaźnika na każdą oś** (OFF/DEF RTG,
Four Factors, Morey Score, tempo, udział trójek i inne). Kolor punktu to zawsze
bilans na 100 posiadań, przerywane linie pokazują średnią ligi, a podpisy
drużyn omijają się nawzajem — przy kolizji znika etykieta, nie punkt.

### Filtry

Pasek filtrów na stronie głównej i w profilu zawodnika: **Sezon / Ostatnie 5 /
Dom / Wyjazd / Wygrane / Porażki** oraz wybór pojedynczego meczu.
Przeglądarka dostaje surowe wiersze meczowe **wszystkich drużyn ligi**
(`league_games.json`), więc miejsce w lidze jest przeliczane dla tego samego
wycinka u rywali — filtr „tylko wyjazdy" pokazuje rangę wśród wyjazdowych
wyników całej ligi, a nie rangę sezonową.

Ratingi skorygowane o siłę rywala (AdjORTG/AdjDRTG/AdjNET/SOS) oraz percentyle
zawodników wymagają pełnego terminarza, więc zawsze dotyczą całego sezonu —
jest to zaznaczone przy odpowiednich sekcjach.

### Pliki danych

```
docs/data/
  meta.json           klub, sezon, lista drużyn, źródła, ostrzeżenia
  league.json         sezonowe wskaźniki wszystkich drużyn + średnie ligowe
  league_games.json   surowe wiersze meczowe całej ligi (podstawa filtrów)
  club.json           dane klubu i lista jego meczów
  players.json        kafle zawodników klubu
  player/<klucz>.json profil zawodnika wraz z jego rzutami
  lineups.json        piątki klubu
  lineup/<id>.json    piątka: mecze i pojedynki z piątkami rywali
  pairs.json          duety
  shots.json          wszystkie rzuty klubu
  glossary.json       słownik metryk
  pbp/<matchId>.json  pełne play-by-play meczu klubu wraz z posiadaniami
```

Każde zdarzenie w `pbp/` ma rozwiązany klucz zawodnika, więc filtr „tylko ten
zawodnik" nie wymaga dopasowywania po nazwisku. Obok zdarzeń zapisane są
posiadania: numer, drużyna w ataku, zakres zdarzeń, punkty i składy obu drużyn
na parkiecie — to baza pod przyszłe widoki (np. wszystkie posiadania danej
piątki albo wybranego duetu).

### Uruchomienie lokalne

```bash
cd docs
python -m http.server 8765
# http://127.0.0.1:8765/
```

### Publikacja

`.github/workflows/pages.yml` publikuje katalog `docs/` na GitHub Pages przy
każdym pushu na `main`. Krok `configure-pages` ma ustawione `enablement: true`,
więc przy pierwszym uruchomieniu sam włącza Pages przez API i ustawia źródło
na GitHub Actions — nie trzeba niczego klikać w ustawieniach repozytorium.

Workflow można też odpalić ręcznie: **Actions → Publikacja portalu → Run
workflow**. Wszystkie ścieżki w portalu są względne, więc działa on zarówno
w katalogu głównym domeny, jak i w podkatalogu `/basket_lab/`.

`.github/workflows/refresh.yml` dociąga nowe mecze po kolejce (poniedziałek
i wtorek rano) i commituje przeliczone dane.

---

## 3. Uwagi o danych

* Play-by-play PZKosz nie zawiera współrzędnych rzutów — mapy rzutów powstają
  wyłącznie z LiveStats.
* Ratingi piątek są bardzo wrażliwe na próbę; portal wysyła **wszystkie**
  piątki, a próg posiadań ustawia się w interfejsie (domyślnie bez progu),
  przy każdej wartości widoczna jest liczba posiadań.
* Rozbicie wpływu zawodnika (model box-score) wymaga kilkudziesięciu graczy
  z odpowiednim stażem — na początku sezonu sekcja pokazuje komunikat zamiast
  liczb, zamiast udawać precyzję, której nie ma.
* `meta.json` zawiera listę ostrzeżeń z ostatniego przeliczenia (np. mecz
  z niekompletnym play-by-play), więc problemy z danymi są widoczne, a nie
  ukryte.

Inspiracje: KenPom, EvanMiya, Dunks & Threes, DataBallr, Moreyball101,
Puls Basketu, NBA.com/stats.
