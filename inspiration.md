1. Rdzeń całego portalu: „KenPom dla 1 LM”

To powinien być ekran, który otwierasz i w 15 sekund rozumiesz ligę.

Dla każdej drużyny:

1LM Rating

AdjNET = AdjORTG - AdjDRTG

gdzie:

AdjORTG = ile punktów / 100 posiadań zdobywałaby drużyna przeciwko przeciętnej drużynie 1 LM.

AdjDRTG = ile traciłaby przeciwko przeciętnemu atakowi 1 LM.

KenPom właśnie w ten sposób koryguje efficiency o jakość przeciwnika, a jego główne ratingi pokazują Net Rating, ORtg, DRtg, adjusted tempo, luck i strength of schedule.

To jest szczególnie ważne w małej lidze. Samo:

Poznań ORTG 119

niewiele mówi.

Znacznie ciekawsze jest:

ORTG 119
AdjORTG 116.8 – #3 w lidze
przeciwnicy: 4. najtrudniejszy terminarz

Do tego Four Factors:

Atak	Obrona
eFG%	Opp eFG%
TOV%	Forced TOV%
ORB%	DREB%
FTr	Opp FTr

KenPom traktuje właśnie shooting, turnovers, rebounding i free throws jako fundamentalne komponenty efektywności.

Puls Basketu już pokazuje m.in. ORTG, DRTG, NetRtg, Pace, TS%, eFG%, 3PR, FTR, AST%, rebound percentages i TOV%, więc taki poziom bazowy jest zdecydowanie osiągalny.

2. Player Impact — najważniejsza rzecz, której brakuje zwykłym statystykom

Tutaj wzorowałbym się najmocniej na EvanMiya + Dunks & Threes.

Nie:

Blanton: 16 pkt, 7 zb, 9 ast.

Tylko:

Devontae Blanton
1LM Impact: +5.8 / 100 poss
Offensive Impact: +4.7
Defensive Impact: +1.1
87. percentyl ligi

EvanMiya BPR interpretuje dokładnie w ten sposób: jako oczekiwaną zmianę punktów na 100 posiadań wynikającą z obecności zawodnika, rozdzielając OBPR i DBPR i uwzględniając jakość partnerów oraz przeciwników.

Ale zrobiłbym to etapami

Na początku:

Impact v1 = stabilized box impact + adjusted on/off

Potem, po zebraniu kilkudziesięciu meczów:

Impact v2 = Ridge Adjusted Plus Minus + box-score prior

czyli coś zbliżonego ideowo do BPR/EPM.

Dunks & Threes pokazuje, jak użyteczny jest jeden główny rating EPM, ale zawsze rozbity na offense i defense, a obok USG, scoring, shooting, rebounding, handling itd.

Bardzo ważna rzecz: nie pokazywać samego ratingu

Obok:

+5.8 Impact

powinno być:

dlaczego?

I rozkład:

+5.8
→ Offense +4.7
→ Defense +1.1

a dalej np.:

Offense +4.7
→ Shooting +1.8
→ Creation +1.5
→ Turnovers +0.8
→ Offensive rebounding +0.6

To jest bardzo ciekawy kierunek DataBallr. Ich Six-Factor RAPM decomposes impact m.in. na shooting, turnovers i rebounding po obu stronach parkietu.

3. To, o czym wcześniej rozmawialiśmy: punkty na posiadanie danego gracza

To powinno być jednym z centralnych ekranów.

Dla zawodnika:

gdy jest na parkiecie	wynik
Possessions	64
Team ORTG	127.4
Team DRTG	103.9
Net	+23.5
PPP	1.274
Opp PPP	1.039
eFG	59.4%
TOV%	12.1%
ORB%	36.4%

A pod spodem:

ON

127.4 ORTG / 103.9 DRTG

OFF

105.8 ORTG / 112.7 DRTG

ON/OFF

+30.4 Net / 100 possessions

Puls Basketu ma już ORTG(on), DRTG(on), Net(on), off-court ratings i Net+/− jako część swoich statystyk zawodników.

My powinniśmy pójść dalej i zrobić adjusted on/off, tak jak EvanMiya: wynik skorygowany o przeciwników spotykanych przez zawodnika.

To rozwiązuje klasyczny problem:

rezerwowy ma +18 Net Rating, ale gra głównie przeciwko rezerwowym przeciwnika.

4. Lineup Lab — moim zdaniem potencjalnie najlepsza część całej aplikacji

Play-by-play PZKosz zawiera dokładne zmiany zawodników wraz z timestampem. Przykładowo w meczu Poznań–Opole mamy wpisy o zejściach i wejściach przy 7:02, 4:49 itd.

To oznacza, że możemy rekonstruować stinty.

Czyli:

Nowicki – Stankowski – Blanton – Siewruk – Dimanochie

Czas: 8:42
Poss: 18
Score: 27–14

ORTG: 150.0
DRTG: 77.8
NET: +72.2

Ale jeszcze ciekawsze:

2-man combinations

EvanMiya mierzy pary zawodników, ich ORtg, DRtg, adjusted margin oraz Chemistry — czyli o ile lepiej drużyna gra, kiedy dana para występuje razem, niż wynikałoby to z ich indywidualnych wyników.

U nas:

Blanton + Siewruk

Together: +18.4

Blanton without Siewruk: +4.1
Siewruk without Blanton: +2.7

Synergy: +11.6

To jest dla trenera znacznie ciekawsze niż +/-.

5. Lineup Builder

Jeszcze mocniejszy pomysł z EvanMiya.

Trener klika pięciu zawodników:

PG: Malesa
SG: Stankowski
SF: Blanton
PF: Siewruk
C: Dimanochie

Portal pokazuje:

Observed:

+16.2 NET

ale również:

Projected

+11.8 NET

Offense: 119
Defense: 107

oraz:

Creation ★★★★☆
Shooting ★★★★☆
Rim pressure ★★★☆☆
Ball security ★★★★☆
Rebounding ★★★★★
Spacing ★★★★☆
Defense ★★★☆☆

EvanMiya przewiduje efektywność piątki nawet przy małej albo zerowej liczbie wspólnych posiadań, wykorzystując umiejętności poszczególnych zawodników oraz balance pozycji i ról.

Na początku sezonu w 1 LM byłoby to niesamowicie przydatne, bo każda realna piątka ma mały sample.

6. DataBallr: karta zawodnika zamiast tabeli statystyk

To jest element, który moim zdaniem zrobiłby największą różnicę wizualną.

Profil:

Devontae Blanton

Overall Impact +5.2 — 94 pct

SCORING

16.0 PPG
61 TS%
+6.1 rTS

CREATION

31% Usage
38 AST%
1.8 AST/TOV
XX points created / 100

SHOT PROFILE

RIM ███████

MID ██

3PT ███

FT ████

DEFENSE

Forced TO
STL
BLK
DREB
On-ball foul rate

IMPACT

Off +4.1
Def +1.1
Total +5.2

DataBallr bardzo dobrze prezentuje właśnie profil zawodnika przez relative TS, creation, shot profile, defensive disruption, rebounding i RAPM, plus historię sezon po sezonie i percentyle pozycyjne.

Percentyle są kluczowe.

Nie:

AST% 27.6

tylko:

AST% 27.6
91. percentyl wśród guardów 1 LM

To trener od razu rozumie.

7. Shooting Lab

Tutaj wykorzystałbym dane Genius/FIBA LiveStats, o które pytałeś wcześniej.

Najpierw zwykłe strefy:

RIM
Restricted Area

PAINT
non-rim

SHORT MID

LONG MID

CORNER 3

ABOVE BREAK 3

Dla każdej:

FGA
FG%
eFG
PPS
frequency
league avg
percentile.

Czyli np.:

Siewruk
Corner 3
43%
liga 34%
+9 pp
88 percentile

Ale jeszcze ciekawiej:

Shot diet

Rim + 3 = 78% prób

czyli coś, co nazwałbym np.

Morey Score

pokazujący, czy zawodnik/drużyna generuje wartościowe typy rzutów.

8. Expected Shot Quality — wersja możliwa dla 1 LM

DataBallr rozdziela:

Shot Quality – jak dobre rzuty tworzysz

od:

Shot Making – jak dobrze trafiasz ponad oczekiwanie.

Ich pełny model korzysta m.in. z lokalizacji rzutu, odległości obrońcy, rodzaju rzutu i innych danych trackingowych, których w 1 LM nie będziemy mieli.

Ale możemy zbudować xPTS Lite.

Na podstawie:

lokalizacji rzutu
strefy
2P/3P
transition/halfcourt, jeżeli PBP pozwoli to określić
czasu akcji
offensive rebound → putback
asysty
wyniku meczu
kwarty.

Model:

xPTS = P(expected points | shot zone, context)

I wtedy:

Shot Creation

1.15 xPTS / shot

Shot Making

1.27 actual PPS

Shot Making Added

+0.12 PPS

Czyli:

ofensywa generuje przeciętne rzuty, ale zawodnik trafia je znakomicie

versus:

zawodnik ma wysoką skuteczność głównie dlatego, że dostaje łatwe rzuty.

9. Historia zawodnika mecz po meczu

Tutaj wziąłbym rozwiązanie z Dunks & Threes/DataBallr.

Wykres:

Player Impact by Game

M1 +1.2
M2 +2.7
M3 +3.1
M4 +3.8
M5 +4.5

ale obok:

rolling 5
rolling 10
season
weighted recent form

Dunks & Threes wykorzystuje model, który inaczej waży wcześniejsze i nowsze występy i próbuje oddzielić zmianę umiejętności od szumu małej próbki.

W 1 LM moglibyśmy mieć:

Form

last 5 Impact: +7.1

Season Impact: +3.8

Δ +3.3

🔥 Trending Up

10. „Who makes whom better?”

To bym mocno wyeksponował.

Profil Blantona:

Best partners
Partner	razem NET	osobno	synergy
Siewruk	+18.4	+4.5	+13.9
Dimanochie	+14.1	+5.7	+8.4
Stankowski	+11.3	+7.1	+4.2
Players improved most by Blanton

Siewruk
+8.1 pts/100

Stankowski
+5.7

Dimanochie
+4.2

EvanMiya ma bardzo podobną koncepcję „Above / Below Average” oraz teammate chemistry.

11. Kill Shots

To jest mały pomysł z EvanMiya, który koniecznie bym wziął.

Kill Shot = seria minimum 10:0.

EvanMiya mierzy liczbę takich runów zdobytych, straconych i ich bilans.

Dla drużyny:

Kill Shots / game: 1.6
Allowed: 0.7

A dalej możemy zrobić coś jeszcze lepszego:

Run killers

Którzy zawodnicy najczęściej pojawiają się przy przerwaniu runu przeciwnika.

Run starters

Kto jest na boisku przy początku 8:0 / 10:0.

Momentum lineups

Które piątki najczęściej robią serie.

Idealne do analizy zmian trenera.

12. Possession Explorer

To byłaby funkcja typowo „dla sztabu”.

Mecz można przejrzeć:

Poss 43
06:50 Q3

Lineup:
Malesa
Samsonowicz
Kluj
Rompa
Siewruk

54–40

Siewruk
3PT MADE
Assist Blanton

Possession value: 3.0
xPTS: 1.18

PZKosz daje timestampy, rodzaj rzutu, wynik, asysty, zbiórki, przechwyty, bloki i zmiany.

To pozwala potem kliknąć:

„pokaż wszystkie posiadania piątki X”

albo:

„wszystkie possessions Blantona + Siewruka”.

13. Scouting rywala

Przed meczem:

SCOUT — Miasto Szkła Krosno

Team identity

Tempo: #14
ORTG: #3
DRTG: #8

Offensive profile

Rim 29%
Midrange 18%
3PT 44%
FT 9%

Four Factors

eFG #2
TOV #12
ORB #3
FTR #10

Key lineups

najlepsza piątka

Players

top creator
top shooter
rim pressure
offensive rebounder

Tendencies

3P frequency
fastbreak
second chance
turnovers
foul drawing

Weakness

Opp ORB 37% — #15

I od razu trener wie:

atakować deskę.

14. Bardzo ciekawa rzecz: „style map”

Zamiast rankingu tylko lepszy/gorszy:

              FAST
               ↑
transition     │      transition + shooting
               │
RIM ←──────────┼──────────→ 3PT
               │
post/rebound   │      halfcourt spacing
               ↓
              SLOW

Każda drużyna 1 LM jako punkt.

Możemy też zrobić PCA/cluster analysis i automatycznie tworzyć archetypy:

Fast & Physical

Five-Out Shooting

Halfcourt Creation

Paint Dominant

Defense & Rebound

High Variance 3PT

To jest dużo bardziej użyteczne scoutingowo niż pozycja w tabeli.

15. Moreyball101 — bardzo ważny UX

To nie jest najlepszy serwis analityczny z tej grupy, ale ma świetną ideę:

tłumaczyć statystyki normalnym językiem.

Strona definiuje m.in. BPM, VORP, eFG%, TS%, USG%, AST%, TOV%, ORB%, DRB%, ORtg i DRtg.

U nas każda metryka powinna mieć ?.

Na przykład:

USG 27.4%

Około 27% posiadań drużyny kończy się akcją tego zawodnika, kiedy znajduje się na parkiecie.

Net +12.4

Drużyna zdobywa o około 12 punktów więcej niż przeciwnik na każde 100 posiadań z zawodnikiem na boisku.

To bardzo zwiększa użyteczność również dla zarządu, kibiców i mediów.