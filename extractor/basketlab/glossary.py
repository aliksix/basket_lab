"""Słownik metryk - źródło treści dla dymków z wyjaśnieniami w portalu.

Każdy wpis ma krótką nazwę, jedno zdanie "co to znaczy" i - tam, gdzie to
pomaga - zdanie "jak czytać". Język celowo potoczny: portal oglądają również
kibice i zarząd, nie tylko sztab szkoleniowy.
"""

from __future__ import annotations

GLOSSARY: dict[str, dict[str, str]] = {
    "ortg": {
        "label": "OFF RTG",
        "full": "Offensive Rating",
        "desc": "Punkty zdobyte na 100 posiadań.",
        "how": "Odporny na tempo gry — inaczej niż średnia punktów na mecz.",
    },
    "drtg": {
        "label": "DEF RTG",
        "full": "Defensive Rating",
        "desc": "Punkty stracone na 100 posiadań.",
        "how": "Im niżej, tym lepiej.",
    },
    "net": {
        "label": "NET RTG",
        "full": "Net Rating",
        "desc": "Różnica między atakiem a obroną na 100 posiadań.",
        "how": "+10 oznacza, że na każde 100 posiadań drużyna wygrywa dziesięcioma punktami.",
    },
    "adj_ortg": {
        "label": "AdjORTG",
        "full": "Adjusted Offensive Rating",
        "desc": "Atak skorygowany o siłę obron, z którymi grała drużyna.",
        "how": "Ile punktów na 100 posiadań drużyna zdobywałaby przeciwko przeciętnej obronie ligi.",
    },
    "adj_drtg": {
        "label": "AdjDRTG",
        "full": "Adjusted Defensive Rating",
        "desc": "Obrona skorygowana o siłę ataków rywali.",
        "how": "Ile punktów na 100 posiadań drużyna traciłaby przeciwko przeciętnemu atakowi ligi.",
    },
    "adj_net": {
        "label": "AdjNET",
        "full": "Adjusted Net Rating",
        "desc": "AdjORTG minus AdjDRTG — najlepszy pojedynczy wskaźnik siły drużyny.",
        "how": "Tak samo jak NET, ale bez premii za łatwy terminarz.",
    },
    "sos": {
        "label": "SOS",
        "full": "Strength of Schedule",
        "desc": "Średni AdjNET rywali, z którymi drużyna zagrała.",
        "how": "Wartości dodatnie oznaczają terminarz trudniejszy od przeciętnego.",
    },
    "pace": {
        "label": "TEMPO",
        "full": "Pace",
        "desc": "Liczba posiadań na 40 minut gry.",
        "how": "Wysokie tempo to więcej akcji, a nie automatycznie lepsza gra.",
    },
    "min_together": {
        "label": "Min razem",
        "full": "Minuty wspólnej gry",
        "desc": "Ile minut ta piątka spędziła na parkiecie w tym samym składzie.",
        "how": "Kilkanaście minut to jeszcze mała próba — ratingi czytaj z ostrożnością.",
    },
    "poss": {
        "label": "POSIADANIA",
        "full": "Possessions",
        "desc": "Liczba posiadań policzona z play-by-play.",
        "how": "Zbiórka w ataku przedłuża to samo posiadanie, nie zaczyna nowego.",
    },
    "efg": {
        "label": "eFG%",
        "full": "Effective Field Goal %",
        "desc": "Skuteczność z gry, w której trójka liczy się jako półtora trafienia.",
        "how": "50% to mniej więcej średni poziom — poniżej 48% robi się problem.",
    },
    "ts": {
        "label": "TS%",
        "full": "True Shooting %",
        "desc": "Skuteczność łączna: rzuty za 2, za 3 i wolne w jednej liczbie.",
        "how": "Najuczciwsza miara efektywności rzutowej zawodnika.",
    },
    "rts": {
        "label": "rTS%",
        "full": "Relative True Shooting",
        "desc": "TS% zawodnika minus średnie TS% ligi.",
        "how": "+5 oznacza, że zawodnik rzuca dużo skuteczniej niż przeciętny gracz 1 LM.",
    },
    "tov_rate": {
        "label": "TOV%",
        "full": "Turnover Rate",
        "desc": "Odsetek posiadań zakończonych stratą.",
        "how": "Im niżej, tym lepiej; poniżej 14% to bardzo dobry wynik.",
    },
    "orb_rate": {
        "label": "ORB%",
        "full": "Offensive Rebound %",
        "desc": "Odsetek własnych niecelnych rzutów zebranych w ataku.",
        "how": "Każda zbiórka w ataku to dodatkowa szansa w tym samym posiadaniu.",
    },
    "drb_rate": {
        "label": "DRB%",
        "full": "Defensive Rebound %",
        "desc": "Odsetek niecelnych rzutów rywala zebranych w obronie.",
        "how": "Kończenie akcji obronnych zbiórką to czwarty z Four Factors.",
    },
    "ft_rate": {
        "label": "FTr",
        "full": "Free Throw Rate",
        "desc": "Liczba rzutów wolnych przypadająca na 100 rzutów z gry.",
        "how": "Pokazuje, jak często drużyna atakuje kosz i wymusza faule.",
    },
    "tpar": {
        "label": "3PAr",
        "full": "Three Point Attempt Rate",
        "desc": "Odsetek rzutów z gry oddanych zza linii 6.75.",
        "how": "Opisuje styl gry, nie jej jakość.",
    },
    "usage": {
        "label": "USG%",
        "full": "Usage Rate",
        "desc": "Odsetek posiadań drużyny kończonych akcją zawodnika, gdy jest on na parkiecie.",
        "how": "20% to udział przeciętny; powyżej 28% mówimy o pierwszej opcji ofensywnej.",
    },
    "ast_rate": {
        "label": "AST%",
        "full": "Assist Rate",
        "desc": "Odsetek trafień kolegów z boiska, przy których zawodnik zaliczył asystę.",
        "how": "Miara kreowania gry niezależna od liczby minut.",
    },
    "ast_to": {
        "label": "AST/TO",
        "full": "Assist to Turnover",
        "desc": "Stosunek asyst do strat.",
        "how": "Powyżej 2.0 to bardzo pewne prowadzenie gry.",
    },
    "stl_rate": {
        "label": "STL%",
        "full": "Steal Rate",
        "desc": "Odsetek posiadań rywala zakończonych przechwytem zawodnika.",
    },
    "blk_rate": {
        "label": "BLK%",
        "full": "Block Rate",
        "desc": "Odsetek rzutów za 2 rywala zablokowanych przez zawodnika.",
    },
    "trb_rate": {
        "label": "TRB%",
        "full": "Total Rebound %",
        "desc": "Odsetek wszystkich zbiórek dostępnych przy zawodniku na parkiecie.",
    },
    "three_pct": {
        "label": "3P%",
        "full": "Three Point %",
        "desc": "Skuteczność rzutów za 3 punkty.",
    },
    "ft_pct": {
        "label": "FT%",
        "full": "Free Throw %",
        "desc": "Skuteczność rzutów osobistych.",
    },
    "ftr": {
        "label": "FTr",
        "full": "Free Throw Rate",
        "desc": "Rzuty wolne przypadające na 100 rzutów z gry — miara agresji w ataku.",
    },
    "on_ortg": {
        "label": "ORTG (on)",
        "full": "On-court Offensive Rating",
        "desc": "Atak drużyny na 100 posiadań, gdy zawodnik jest na parkiecie.",
    },
    "on_drtg": {
        "label": "DRTG (on)",
        "full": "On-court Defensive Rating",
        "desc": "Obrona drużyny na 100 posiadań, gdy zawodnik jest na parkiecie.",
    },
    "on_net": {
        "label": "NET (on)",
        "full": "On-court Net Rating",
        "desc": "Bilans drużyny na 100 posiadań z zawodnikiem na boisku.",
    },
    "off_net": {
        "label": "NET (off)",
        "full": "Off-court Net Rating",
        "desc": "Bilans drużyny na 100 posiadań, gdy zawodnik siedzi na ławce.",
    },
    "diff": {
        "label": "ON/OFF",
        "full": "On/Off Differential",
        "desc": "O ile lepiej drużyna gra z zawodnikiem na parkiecie niż bez niego.",
        "how": "Przy małej próbce potrafi mocno skakać — patrz na liczbę posiadań obok.",
    },
    "adj_net_player": {
        "label": "Adj ON/OFF",
        "full": "Adjusted On/Off",
        "desc": "On/off skorygowany o siłę rywali, przeciwko którym zawodnik grał.",
        "how": "Rozwiązuje problem rezerwowego, który gra głównie przeciwko rezerwowym rywala.",
    },
    "impact": {
        "label": "IMPACT",
        "full": "BasketLab Impact",
        "desc": "Szacowana zmiana bilansu drużyny na 100 posiadań wynikająca z obecności zawodnika.",
        "how": "Miks skorygowanego on/off i modelu box-score dopasowanego do 1 LM; przy małej próbce ciągnięty do zera.",
    },
    "impact_off": {
        "label": "IMPACT OFF",
        "full": "Offensive Impact",
        "desc": "Ofensywna część wpływu zawodnika, w punktach na 100 posiadań.",
    },
    "impact_def": {
        "label": "IMPACT DEF",
        "full": "Defensive Impact",
        "desc": "Defensywna część wpływu zawodnika, w punktach na 100 posiadań.",
    },
    "morey": {
        "label": "MOREY SCORE",
        "full": "Jakość doboru rzutów",
        "desc": "Odsetek rzutów oddanych spod kosza albo zza linii 6.75.",
        "how": "Wysoka wartość oznacza dobór rzutów o najlepszej opłacalności.",
    },
    "pps": {
        "label": "PPS",
        "full": "Points Per Shot",
        "desc": "Punkty zdobyte na jeden rzut z gry w danej strefie.",
    },
    "xpts": {
        "label": "xPTS",
        "full": "Expected Points",
        "desc": "Punkty, jakich należałoby oczekiwać po takim rozkładzie rzutów przy ligowej skuteczności.",
        "how": "Różnica między PPS a xPTS pokazuje, ile zawodnik dokłada samym trafianiem.",
    },
    "shot_making": {
        "label": "SHOT MAKING",
        "full": "Shot Making Added",
        "desc": "Punkty na rzut ponad to, czego oczekiwalibyśmy po strefach, z których rzuca.",
        "how": "Wartość dodatnia: trafia trudniejsze rzuty niż przeciętny gracz ligi.",
    },
    "kill_shots": {
        "label": "KILL SHOTS",
        "full": "Kill Shots",
        "desc": "Liczba serii co najmniej 10 punktów bez odpowiedzi rywala.",
    },
    "kill_allowed": {
        "label": "KILL SHOTS STRACONE",
        "full": "Kill Shots Allowed",
        "desc": "Liczba serii 10:0 straconych na rzecz rywala.",
    },
    "clutch": {
        "label": "CLUTCH",
        "full": "Clutch time",
        "desc": "Ostatnie 5 minut czwartej kwarty i cała dogrywka, gdy różnica punktowa nie przekracza 5.",
        "how": "Liczone od stanu na początku posiadania — mecz wchodzi i wychodzi z clutch time w trakcie końcówki.",
    },
    "clutch_ortg": {
        "label": "CLUTCH OFF",
        "full": "Clutch Offensive Rating",
        "desc": "Punkty na 100 posiadań zdobywane w końcówkach przy wyrównanym wyniku.",
    },
    "clutch_drtg": {
        "label": "CLUTCH DEF",
        "full": "Clutch Defensive Rating",
        "desc": "Punkty na 100 posiadań tracone w końcówkach przy wyrównanym wyniku.",
    },
    "fga_long_rate": {
        "label": "%FGA +15",
        "full": "Udział rzutów z długich akcji",
        "desc": "Odsetek rzutów z gry oddanych w akcjach trwających co najmniej 15 sekund.",
        "how": "Liczone tylko z pierwszej szansy — rzuty po własnej zbiórce w ataku są pomijane, "
               "bo sztucznie wydłużałyby akcję.",
    },
    "ppp_long": {
        "label": "PPP +15",
        "full": "Punkty na posiadanie w długich akcjach",
        "desc": "Punkty na jedno posiadanie trwające co najmniej 15 sekund.",
        "how": "Miara gry w ustawionej obronie: pokazuje, ile zespół wyciąga, gdy nie dostaje łatwych punktów "
               "z kontry. Bez punktów zdobytych po zbiórce w ataku.",
    },
    "long_share": {
        "label": "UDZIAŁ DŁUGICH AKCJI",
        "full": "Udział akcji 15+ sekund",
        "desc": "Odsetek posiadań, w których pierwsza szansa trwała co najmniej 15 sekund.",
        "how": "Wysoka wartość oznacza grę przeciwko ustawionej obronie, niska - dużo szybkiego ataku.",
    },
    "ppp_ind": {
        "label": "PPP",
        "full": "Punkty na posiadanie zawodnika",
        "desc": "Punkty podzielone przez posiadania zakończone jego akcją: rzut, rzuty wolne albo strata.",
        "how": "Wzór: PTS / (FGA + 0.44 × FTA + TOV). Mierzy, ile zespół dostaje z każdej akcji oddanej temu zawodnikowi.",
    },
    "ppp_on": {
        "label": "PPP ON",
        "full": "PPP zespołu na parkiecie",
        "desc": "Punkty zespołu na jedno posiadanie, gdy zawodnik jest na boisku.",
        "how": "To samo co ORTG (on) podzielone przez 100 — opisuje cały atak, nie tylko jego akcje.",
    },
    "scoring_100": {
        "label": "PUNKTY / 100",
        "full": "Punkty na 100 posiadań",
        "desc": "Wolumen zdobywania punktów niezależny od liczby minut i tempa gry.",
    },
    "synergy": {
        "label": "SYNERGIA",
        "full": "Chemistry",
        "desc": "O ile lepszy jest bilans pary niż suma tego, co każdy z zawodników robi osobno.",
    },
    "plus_minus": {
        "label": "+/-",
        "full": "Plus Minus",
        "desc": "Różnica punktowa zanotowana w czasie gry zawodnika.",
    },
    "pts": {"label": "PKT / MECZ", "full": "Punkty na mecz", "desc": "Średnia punktów w wybranym wycinku."},
    "trb": {"label": "ZB / MECZ", "full": "Zbiórki na mecz", "desc": "Średnia zbiórek w wybranym wycinku."},
    "ast": {"label": "AS / MECZ", "full": "Asysty na mecz", "desc": "Średnia asyst w wybranym wycinku."},
}

ZONE_GLOSSARY = {
    "RIM": "Rzuty z odległości do 1.8 m od obręczy — najbardziej opłacalna strefa.",
    "PAINT": "Pole ograniczone poza bezpośrednim sąsiedztwem obręczy.",
    "SHORT_MID": "Średni dystans do 4.5 m od kosza.",
    "LONG_MID": "Daleki średni dystans, tuż przed linią za 3 — statystycznie najgorszy rzut.",
    "CORNER_3": "Trójka z narożnika — najkrótsza trójka na boisku.",
    "ABOVE_BREAK_3": "Trójka ze skrzydła albo z czoła.",
}
