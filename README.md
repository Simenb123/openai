# RAG Assistant (Norsk revisjon)

Målet med repoet er å bygge en liten *RAG-prototype* for revisjonskilder (ISA/ISQM, lov/forskrift, dommer, artikler osv.), med:

- **Standardisert kildebibliotek** (`kildebibliotek.json`)
- **Ingest/chunking** med **ankere** (f.eks. `§1-1`, `§1-1(1)[a]`, `P8`, `A1`)
- **Indeksering i Chroma** (`ragdb/`)
- **Spørring via CLI** (`run_qa_cli.py`)
- **Admin-GUI** for å administrere kilder og relasjoner (`run_admin_gui.py`)

Repoet er laget for å kunne videreutvikles til et mer komplett oppsett for norske revisorer, der revisjonsstandarder er sentrale og kobles mot lov/forskrift, forarbeider, dommer, Finanstilsynets rapporter, fagartikler og lovkommentarer.

## 1) Installer

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Lag `.env` i rot (ikke commit):

```env
OPENAI_API_KEY=...
# Valgfritt:
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
RAG_DB_PATH=ragdb
RAG_COLLECTION=revisjon
```

## 2) Kilder

Du kan legge kilder inn på to måter:

### A) Enkelt: filer direkte i `kilder/`

Eksempel:
- `kilder/isa230.txt`
- `kilder/revisorloven` (ingen endelse – behandles som tekst)
- `kilder/forskrift_revisorloven` (ingen endelse)

Dette passer fint for en rask pilot.

### B) Anbefalt: standardformat (én mappe per kilde)

Dette gjør import + vedlikehold mye mer ryddig når antall kilder vokser.

Struktur:

```
kilder/
  RL/
    source.json        # valgfri
    revisorloven.txt   # .txt/.pdf/.docx eller ingen endelse
  RF/
    source.json
    revisorforskriften.txt
  ISA-230/
    source.json
    isa230.txt
```

`source.json` er valgfri, men anbefales. Eksempel:

```json
{
  "id": "ISA-230",
  "title": "ISA 230 Revisjonsdokumentasjon",
  "doc_type": "ISA",
  "tags": ["isa", "dokumentasjon"],
  "metadata": {
    "language": "no",
    "origin": "Revisorforeningen"
  }
}
```

**Import til `kildebibliotek.json`:**
- I GUI: knapp **"Importer kildemap..."** (Kilder-fanen)
- Eller CLI:

```bash
python run_import_sources.py kilder --library kildebibliotek.json
```

Merk:
- Importen **indekserer ikke**. Etter import må du indeksere (GUI eller `run_build_index.py`).
- Du trenger ikke bruke `.txt.txt`. Enten:
  - lag filene med `.txt`, eller
  - bruk filer uten endelse (de tolkes som tekst).


## 3) Kildebibliotek + relasjoner (GUI)

Start GUI:

```bash
python run_admin_gui.py
```

### Kilder

- Legg til en kilde (ID, Type, Tittel, filer, tags)
- Lagre bibliotek

### Relasjoner

Du kan legge til relasjoner:
- dokumentnivå: `Revisorloven -> Revisorforskriften`
- ankernivå: `Revisorloven §1-1 -> Revisorforskriften §1-1`
- **ledd/bokstav-nivå**: `Revisorloven §1-1(1) -> Revisorforskriften §1-1(1)` eller `... §1-1(1)[a]`

### Ankerliste (autocomplete + valg i GUI)

Nytt i D3:
- I **Relasjoner**-fanen har du nå også **trevisning** av ankere (paragraf → ledd → bokstav / P → underpunkt).
  Dobbelklikk på et anker i treet for å fylle ut feltet.

Nytt i D4:
- **Relasjonstype-forslag** basert på dokumenttype (ISA/ISQM, lov/forskrift, dom, tilsyn, kommentar osv.).
  Du får:
  - knapper med anbefalte relasjonstyper
  - kort forklaring av valgt relasjonstype
  - hint hvis du har valgt en utypisk retning (f.eks. LOV → FORSKRIFT vs. vanlig FORSKRIFT → LOV)
  - knapp **"Bytt Fra/Til"** for å snu retningen raskt




Nytt i D5:
- **Relasjonsmaler**: Velg en mal og trykk **"Bruk mal"** for å fylle inn anbefalt relasjonstype og (valgfritt) standard notat.
  Hvis malen matcher i "reverse" vil den også **bytte Fra/Til** automatisk (fordi retning er viktig i et relasjonskart).
- **Forslag** (Relasjoner-fanen → tab **"Forslag"**): Skanner teksten i *Fra-kilden* og foreslår relasjoner til *Til-kilden*
  basert på anker-referanser som ser ut som ankere i Til-kilden (f.eks. `§ ...` eller `punkt 8`/`P8`).
  Du kan velge forslag og legge dem inn som relasjoner med ett klikk.

Nytt i D6:
- **Kartlegging** (Relasjoner-fanen → tab **"Kartlegging"**): Et panel som gjør det lettere å bygge relasjoner
  på **ankernivå** (paragraf/ledd/bokstav eller P/A) mellom to kilder.
  Du får:
  - liste over **Fra-ankere** og **Til-ankere**
  - preview av tekstinnhold per anker (leses direkte fra kildefilene)
  - **auto-velg kandidater** basert på anker-hierarki/prefix (nyttig for f.eks. `§1` → `§1-1`, `§1-2` …)
  - "Legg til & neste" for rask paragraf-for-paragraf kartlegging



Nytt i D7 (brukervennlighet):
- **Oversikt/Hurtigstart**-fane som viser en enkel arbeidsflyt (Kilder → Indeks → Relasjoner → QA) med snarveier.
- **Filter** i både **Kilder** og **Relasjoner** (skriv f.eks. `ISA`, `RL`, `§1-1`, `P8`).
- **Redigering av relasjoner**: dobbelklikk på en relasjon i listen for å laste den inn i skjemaet.
  Trykk **"Lagre relasjon"** for å oppdatere, eller **"Avbryt redigering"**.
- **Endringer markeres** med `*` i tittellinjen, og du får spørsmål om å lagre når du lukker GUI.
- **Bakgrunnsoppgaver**: Indeksering og "Skann og foreslå" kjører i bakgrunnen og viser progress nederst.

Nytt i D8 (kartlegging-flyt):
- Kartlegging-panelet viser nå **eksisterende koblinger** for valgt fra-anker, med mulighet for å fjerne.
- **Neste/forrige umappede**: hopp raskt mellom ankere som ikke er mappet ennå.
- **Kun umappede**-filter for å fokusere på det som gjenstår.

Nytt i D9 (import/eksport relasjoner):
- I **Relasjoner**-fanen kan du nå **importere** og **eksportere** relasjoner som **CSV** eller **JSON**.
- CSV eksporteres med **semikolon (;)** som standard (ofte best i norsk Excel).
- Ved import velger du om du vil **erstatte** alle relasjoner, eller **slå sammen (upsert)** inn i eksisterende kart.

Nytt i D10 (kontrollert import + parvis eksport/import):
- Import viser nå en **forhåndsvisning/diff** (nye/oppdaterte/uendrede + hva som fjernes ved "erstatt") før du velger.
- Du kan også **importere/eksportere kun for valgt Fra→Til-par** (knappene "Importer par" / "Eksporter par").
- Kartlegging-listen viser antall koblinger per fra-anker (f.eks. `✓ §1-1 (3)`).

Nytt i D11 (forhåndsvisning-vindu + patch-merge):
- Import åpner nå et eget vindu med **full liste** over **Nye / Oppdateres / Fjernes / Uendret**.
- **Merge** er nå *patch-basert*: uendrede relasjoner røres ikke.
  Dette gjør at du trygt kan re-importere samme fil uten at biblioteket “endres” unødvendig.


Når du indekserer fra `kildebibliotek.json` genereres det også en ankerliste ved siden av bibliotekfilen:

- `kildebibliotek.anchors.json`

Denne inneholder alle ankere som faktisk ble funnet under ingest.

GUI bruker ankerlisten slik:
- **Kilder-fanen:** knapp **"Vis ankere for valgt"** (søk + kopier)
- **Relasjoner-fanen:** knapper **"Vis"** ved ankerfeltene (søk + velg)
- Når du klikker **"Legg til relasjon"** får du **advarsel** dersom anker:
  - ikke finnes i ankerlisten, eller
  - ankerlisten mangler/er tom for kilden

Advarselen blokkerer ikke permanent, men spør om du vil lagre relasjonen likevel (nyttig før reindeksering).

## 4) Indeksering

Anbefalt: bygg indeks fra kildebibliotek:

```bash
python run_build_index.py --library kildebibliotek.json
```

For en *helt konsistent* indeks (anbefales i pilot/beta):

```bash
python run_build_index.py --library kildebibliotek.json --wipe
```

`--wipe` sletter hele collection før indeksering, slik at du ikke får «stale» chunks fra eldre versjoner av kilder.

I GUI:
- **Indekser valgt**: sletter først eksisterende chunks for valgt `source_id`, og bygger på nytt.
- **Indekser alle**: sletter hele collection og bygger på nytt fra biblioteket.

Alternativt: indeksér direkte fra mappe (uten metadata/relasjoner):

```bash
python run_build_index.py kilder
```

Du kan også bruke `--wipe` her hvis du ønsker å starte helt på nytt:

```bash
python run_build_index.py kilder --wipe
```

## 5) Spørsmål (CLI)

```bash
python run_qa_cli.py --show-context "Hva sier ISA 230 om revisjonsdokumentasjon?"
```

`--show-context` skriver ut chunks som ble brukt, med kilde-id og anker.

## 6) Pilot: ISA 230 (én kommando)

Når du vil sjekke at alt fungerer *ende-til-ende* (indeks + retrieval + eval),
kan du kjøre piloten:

```bash
python run_pilot_isa230.py --library kildebibliotek.json --show
```

Hva den gjør:
- velger pilot-kilder (ISA-230 + evt. RL/RF hvis de finnes)
- indekserer disse (purger eksisterende chunks for disse kildene)
- kjører golden-eval fra `golden/golden_isa230_pilot.json`
- lagrer rapport i `reports/golden_isa230_pilot_report.json`

Hvis du vil starte helt rent (sletter hele collection først):

```bash
python run_pilot_isa230.py --library kildebibliotek.json --show --wipe
```

Tips: Hvis du har mange kilder i biblioteket, er piloten en fin måte å iterere
raskt uten å indeksere alt hver gang.

## Om ankere og paragraf/ledd/bokstav

- Under ingest prøver vi å splitte lov/forskrift på linjer som starter med `§ ...`
- Vi lager i tillegg underseksjoner når vi finner:
  - **ledd** på linjestart: `(1)`, `(2)`, ...
  - **bokstavpunkter** på linjestart: `a)`, `b)`, ...
- Hver chunk får `metadata.anchor`

### Ankermønster for lov/forskrift (pilot)

Intern konvensjon (normalisert):

- Paragraf: `§1-1`
- Ledd: `§1-1(1)`
- Bokstav: `§1-1(1)[a]`
- Bokstav uten ledd: `§1-1[a]`

Eksempel relasjoner:

- `RL §1-1(1) -> RF §1-1(1)`
- `RL §1-1(1)[a] -> RF §1-1(1)[a]`

Du kan også spørre naturlig (ankeret ekstraheres):

- "Revisorloven § 1-1 første ledd"
- "§ 1-1 (2) bokstav a"

### D2: Hierarkisk fallback (viktig for vedlikehold)

I praksis vil du ofte starte grovt (paragrafnivå) og bygge mer detaljerte relasjoner senere.

Derfor har vi lagt inn **hierarkisk fallback**:

- Hvis spørsmålet inneholder et veldig spesifikt anker, f.eks. `§1-1(1)[a]`,
  og du kun har lagt inn relasjon på `§1-1` eller `§1-1(1)`, så **matcher relasjonen likevel**.

Ved retrieval i relaterte dokumenter prøver vi også automatisk foreldre-ankere:

`§1-1(1)[a] -> §1-1(1) -> §1-1`

Dette gjør at du kan komme raskt i gang, uten å måtte modellere alle bokstaver/ledd fra dag 1.

### Ankermønster for ISA/ISQM (pilot)

For standarder (ISA/ISQM) lagrer vi ankere slik:

- **Punkt/paragraf**: `P8`, `P9`, `P1.2` (fra linjer som starter med `8.` / `9.` / `1.2.`)
- **Application material**: `A1`, `A2` (fra linjer som starter med `A1`, `A2`, ...)

Dette gjør at du kan lage relasjoner på punktnivå, f.eks.

- `ISA-230 P8 -> RL §1-1`

og deretter spørre:

```bash
python run_qa_cli.py --show-context "ISA 230 pkt 8"
```

## 6) Golden questions (retrieval-evaluering)

Dette er en lettvekts måte å måle om retrieval faktisk treffer riktige kilder/ankere for et sett med representative spørsmål.
Det er spesielt nyttig før du fyller på med mange datakilder.

Eksempel-fil ligger her:

- `golden/golden_isa230.json`

Kjør eval:

```bash
python run_eval_golden.py golden/golden_isa230.json --show
```

Det genereres en rapport (JSON) i:

- `eval_reports/golden_report.json`

Rapporten inneholder per case:
- hvilke kilder/ankere du forventet
- hvilke kilder/ankere som faktisk ble brukt i konteksten
- pass/fail per case

## Testing

Installer avhengigheter:

```bash
pip install -r requirements.txt
```

Kjør testene:

```bash
pytest
```

## GUI er med nå

Ja. `python run_admin_gui.py` starter GUI-en. I tillegg til admin av kilder/relasjoner har den nå en egen tab **QA / Test** der du kan:

- skrive et spørsmål
- hente bare kontekst (ingen LLM-kostnad)
- spørre med LLM
- kjøre golden eval direkte fra GUI

Dette er den enkleste måten å begynne å prøve ut systemet på før du gjør større relasjonsjobb.
