/* Alarmanlagen-Manager – Oberfläche.
 *
 * Eine Regel zieht sich durch: Geändert wird sofort und gespeichert wird
 * sofort. Ein "Speichern"-Knopf, den man beim Einrichten einer Alarmanlage
 * vergessen kann, ist eine Falle – man merkt es erst, wenn nichts meldet.
 */

const Z = {
  konfig: null,
  status: null,
  auswahl: null,
  seite: 'uebersicht',
  ticker: null,
};

const $ = (id) => document.getElementById(id);
const el = (tag, klasse, text) => {
  const k = document.createElement(tag);
  if (klasse) k.className = klasse;
  if (text !== undefined) k.textContent = text;
  return k;
};

async function hole(pfad, optionen) {
  const antwort = await fetch(pfad, optionen);
  if (!antwort.ok) throw new Error(`${antwort.status} ${antwort.statusText}`);
  return antwort.json();
}

async function schicke(pfad, daten) {
  return hole(pfad, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(daten),
  });
}

let tostZeit = null;
function tost(text, schlecht) {
  const k = $('tost');
  k.textContent = text;
  k.className = 'tost an' + (schlecht ? ' schlecht' : '');
  clearTimeout(tostZeit);
  tostZeit = setTimeout(() => { k.className = 'tost'; }, 3200);
}

/* Alle Änderungen laufen hierdurch. Gesammelt wird kurz, damit ein
 * Schieberegler nicht dreißig Schreibvorgänge auslöst. */
let sammelZeit = null;
function konfigSpeichern(teil) {
  Object.assign(Z.konfig, tiefVereinen(Z.konfig, teil));
  clearTimeout(sammelZeit);
  sammelZeit = setTimeout(async () => {
    try {
      const antwort = await schicke('api/konfig', teil);
      Z.konfig = antwort.konfig;
      tost('Gespeichert');
    } catch (fehler) {
      tost('Nicht gespeichert: ' + fehler.message, true);
    }
  }, 350);
}

function tiefVereinen(basis, ueber) {
  const aus = { ...basis };
  for (const [schluessel, wert] of Object.entries(ueber || {})) {
    if (wert && typeof wert === 'object' && !Array.isArray(wert)
        && aus[schluessel] && typeof aus[schluessel] === 'object'
        && !Array.isArray(aus[schluessel])) {
      aus[schluessel] = tiefVereinen(aus[schluessel], wert);
    } else {
      aus[schluessel] = wert;
    }
  }
  return aus;
}

/* ------------------------------------------------------------- Reiter */

document.getElementById('reiter').addEventListener('click', (ereignis) => {
  const knopf = ereignis.target.closest('button[data-seite]');
  if (!knopf) return;
  Z.seite = knopf.dataset.seite;
  document.querySelectorAll('#reiter button').forEach((b) =>
    b.classList.toggle('an', b === knopf));
  document.querySelectorAll('.seite').forEach((s) =>
    s.classList.toggle('an', s.id === 'seite-' + Z.seite));
  if (Z.seite === 'protokoll') { protokollfilterFuellen(); protokollLaden(); }
});

/* ---------------------------------------------------------- Übersicht */

/* Alles, was sonst als roher Schlüssel in der Oberfläche landet.
 *
 * Die Schlüssel selbst bleiben englisch – sie stehen in Home Assistant,
 * in der Konfiguration und im Protokoll, und eine Übersetzung dort würde
 * bei jedem Sprachwechsel Entitäten und Einträge ungültig machen.
 * Übersetzt wird nur, was ein Mensch liest. */
const PANELTEXT = {
  armed_away: 'scharf – niemand zu Hause',
  armed_vacation: 'scharf – Urlaub',
  armed_night: 'scharf – Nacht',
  armed_home: 'teilscharf – jemand zu Hause',
  disarmed: 'entschärft',
};

const PROTOKOLLTEXT = {
  start: 'Start',
  scharf: 'scharf',
  schaltet: 'schaltet scharf',
  entschaerft: 'entschärft',
  voralarm: 'Voralarm',
  ausloesung: 'Auslösung',
  alarm: 'Alarm',
  entwarnung: 'Entwarnung',
  unterdrueckt: 'unterdrückt',
  uebergangen: 'übergangen',
  beruhigt: 'Ruhequelle',
  beobachtet: 'beobachtet',
  verhindert: 'verhindert',
  ueberbrueckt: 'überbrückt',
  quittiert: 'quittiert',
  probe: 'Probebetrieb',
  meldung: 'Meldung',
  hausmodus: 'Hausmodus',
  tuer: 'Tür',
  betrieb: 'Betrieb',
  uebernahme: 'Übernahme',
  hinweis: 'Hinweis',
};

const LINIENTEXT = {
  einbruch: 'Einbruch',
  rauch: 'Rauch',
  wasser: 'Wasser',
  hausmodus: 'Hausmodus',
};

const ZUSTANDSTEXT = {
  disarmed: ['Entschärft', 'entschaerft', '🔓'],
  arming: ['Schaltet scharf', 'laeuft', '⏳'],
  armed_away: ['Scharf', 'scharf', '🛡️'],
  armed_vacation: ['Scharf', 'scharf', '🧳'],
  armed_night: ['Scharf', 'scharf', '🌙'],
  armed_home: ['Teilscharf', 'scharf', '🏠'],
  pending: ['Eintrittsverzögerung', 'laeuft', '⏱️'],
  triggered: ['Alarm', 'alarm', '🚨'],
};

function uebersichtZeichnen() {
  const s = Z.status?.anlage;
  if (!s) return;
  const [name, klasse, symbol] = ZUSTANDSTEXT[s.panel] || ['—', '', '🛡️'];

  $('zustandskachel').className = 'zustandskachel ' + klasse;
  $('zustand-symbol').textContent = symbol;
  $('kopf-symbol').textContent = symbol;
  $('zustand-name').textContent = s.modus_name && s.panel.startsWith('armed')
    ? `${name} – ${s.modus_name}` : name;

  const seit = s.seit ? new Date(s.seit * 1000) : null;
  $('zustand-unter').textContent = seit
    ? `seit ${seit.toLocaleString('de-DE', { weekday: 'short', hour: '2-digit', minute: '2-digit' })}`
    : '';

  if (s.rest_sekunden !== null && s.rest_sekunden !== undefined) {
    const m = Math.floor(s.rest_sekunden / 60);
    const sek = s.rest_sekunden % 60;
    $('zustand-frist').textContent = s.panel === 'arming'
      ? `noch ${m}:${String(sek).padStart(2, '0')} zum Verlassen`
      : s.panel === 'pending'
        ? `noch ${m}:${String(sek).padStart(2, '0')} bis zum Alarm`
        : `noch ${m}:${String(sek).padStart(2, '0')}`;
  } else {
    $('zustand-frist').textContent = '';
  }

  /* Kopfhinweise: alles, was man wissen muss, bevor man sich auf die
   * Anlage verlässt. */
  const hinweise = $('kopf-hinweise');
  hinweise.textContent = '';
  const marke = (text, art) => hinweise.appendChild(el('span', 'marke ' + (art || ''), text));
  if (s.trockenlauf) marke('Trockenlauf – es geht nichts hinaus', 'warn');
  if (!s.automatik) marke('Automatik aus', 'warn');
  if (!s.verbunden) marke('Keine Verbindung zu Home Assistant', 'schlecht');
  if (!Z.status.mqtt?.verbunden) marke('Kein MQTT – kein Bedienfeld', 'schlecht');
  if (s.nachlaufsperre) marke('Nachlaufsperre aktiv');
  if (s.jemand_da) marke('Jemand ist zu Hause', 'gut');
  $('kopf-unter').textContent = `Fassung ${Z.status.version}`;

  /* Modusleiste */
  const leiste = $('modusleiste');
  leiste.textContent = '';
  const modi = [['zuhause', { name: 'Zuhause', symbol: '🏠' }]]
    .concat(Object.entries(Z.konfig.modi)
      .filter(([, m]) => m.aktiv)
      .sort((a, b) => (a[1].reihenfolge || 99) - (b[1].reihenfolge || 99)));
  for (const [schluessel, modus] of modi) {
    const knopf = el('button', 'modusknopf' + (s.hausmodus === schluessel ? ' an' : ''));
    knopf.appendChild(el('span', null, modus.name));
    if (schluessel !== 'zuhause') {
      knopf.appendChild(el('small', null,
        `${modus.ausgehzeit || 0} s hinaus · ${modus.eintrittszeit || 0} s herein`));
    } else {
      knopf.appendChild(el('small', null, 'entschärft'));
    }
    knopf.onclick = async () => {
      const antwort = await schicke('api/schalten',
        { befehl: 'hausmodus', modus: schluessel });
      if (antwort.ok === false) tost(grundText(antwort.grund), true);
      statusLaden();
    };
    leiste.appendChild(knopf);
  }

  /* Karten mit dem Rest */
  const karten = $('uebersicht-karten');
  karten.textContent = '';

  if (s.offene_alarme && Object.keys(s.offene_alarme).length) {
    const karte = el('div', 'karte');
    karte.appendChild(el('h2', null, '🚨 Offene Alarme'));
    for (const eintrag of Object.values(s.offene_alarme)) {
      karte.appendChild(el('div', null, `${eintrag.ort} (${eintrag.linie})`));
    }
    const knopf = el('button', 'knopf klein', 'Quittieren');
    knopf.style.marginTop = '10px';
    knopf.onclick = async () => {
      await schicke('api/schalten', { befehl: 'quittieren' });
      statusLaden();
    };
    karte.appendChild(knopf);
    karten.appendChild(karte);
  }

  const kontakte = el('div', 'karte');
  kontakte.appendChild(el('h2', null, 'Offene Kontakte'));
  if (!s.offene_kontakte?.length) {
    kontakte.appendChild(el('div', 'leer', 'Alles zu.'));
  } else {
    for (const k of s.offene_kontakte) kontakte.appendChild(el('div', null, '• ' + k.name));
  }
  karten.appendChild(kontakte);

  const ausloeser = el('div', 'karte');
  ausloeser.appendChild(el('h2', null, 'Letzter Auslöser'));
  ausloeser.appendChild(el('div', s.ausloeser ? '' : 'leer',
    s.ausloeser || 'Noch keiner.'));
  karten.appendChild(ausloeser);

  $('schalter-trockenlauf').checked = !!s.trockenlauf;
  $('schalter-automatik').checked = !!s.automatik;
}

function grundText(grund) {
  return {
    jemand_da: 'Nicht scharf geschaltet – jemand ist zu Hause.',
    offene_kontakte: 'Nicht scharf geschaltet – es steht etwas offen.',
    unbekannter_modus: 'Diesen Modus gibt es nicht.',
    bereits_scharf: 'Steht schon so.',
    schaltet_bereits: 'Schaltet gerade scharf.',
    bereits_entschaerft: 'Ist schon entschärft.',
    unveraendert: 'Steht schon so.',
    geschaltet: 'Geschaltet.',
    entschaerft: 'Entschärft.',
    unbekannter_befehl: 'Diesen Befehl gibt es nicht.',
    keine_sicherung: 'Es gibt keine Sicherung.',
  }[grund] || grund;
}

$('schalter-trockenlauf').onchange = (e) =>
  schicke('api/schalten', { befehl: 'trockenlauf', an: e.target.checked })
    .then(statusLaden);
$('schalter-automatik').onchange = (e) =>
  schicke('api/schalten', { befehl: 'automatik', an: e.target.checked })
    .then(statusLaden);

/* ------------------------------------------------------------- Melder */

const ARTEN = {
  bewegung: 'Bewegung', kontakt: 'Kontakt', rauch: 'Rauch',
  wasser: 'Wasser', erschuetterung: 'Erschütterung', sonstige: 'sonstige',
};

/* Die Mehrzahl steht ausgeschrieben da. "2 Kontakt im Haus" liest sich wie
 * ein Übersetzungsfehler, und der Satz steht an der auffälligsten Stelle
 * der Seite. */
const ARTEN_MEHRZAHL = {
  bewegung: 'Bewegungsmelder', kontakt: 'Kontakte', rauch: 'Rauchmelder',
  wasser: 'Wassermelder', erschuetterung: 'Erschütterungsmelder',
  sonstige: 'sonstige Melder',
};

/* Welche Melderarten auf welche Linie gehören. Daraus entsteht der
 * Hinweis, was Home Assistant kennt, hier aber fehlt – die nützlichste
 * Auskunft der ganzen Seite: Fünf Rauchmelder im Haus, die in keiner
 * Alarmanlage stehen, fallen sonst niemandem auf. */
const LINIENARTEN = {
  einbruch: ['bewegung', 'kontakt', 'erschuetterung'],
  rauch: ['rauch'],
  wasser: ['wasser'],
};

/* "sonstige" sind meist Diagnosemelder – bei Sven 237 von 291. Vorn stehen
 * sie nur im Weg. */
const ARTORDNUNG = ['rauch', 'wasser', 'bewegung', 'kontakt',
  'erschuetterung', 'sonstige'];

function melderZeichnen() {
  const liste = $('melder-liste');
  /* Welche Karten offen standen, überlebt das Neuzeichnen: Ein Wechsel der
   * Linie klappt sonst die Karte zu, an der man gerade arbeitet. */
  const offen = new Set([...liste.querySelectorAll('details.melder[open]')]
    .map((d) => d.dataset.id));
  liste.textContent = '';

  const alle = Z.konfig.melder || [];
  const suche = ($('melder-filtern')?.value || '').trim().toLowerCase();
  $('melder-zahl').textContent = `${alle.length} eingerichtet`;
  standHinzufuegen();

  if (!alle.length) {
    liste.appendChild(el('div', 'leer',
      'Noch keiner. Oben auswählen – oder unter „Übernahme“ aus den '
      + 'vorhandenen Automationen holen.'));
    return;
  }

  const bereiche = Z.auswahl?.bereiche || {};
  const zustaende = new Map((Z.auswahl?.melder || [])
    .map((m) => [m.entity_id, m.zustand]));

  const gruppen = linienNachOrdnung()
    .concat([['ohne', { name: 'Ohne gültige Linie', reihenfolge: 99 }]]);

  for (const [linieSchluessel, linie] of gruppen) {
    const eigene = alle.filter((m) => {
      const l = Z.konfig.linien[m.linie] ? m.linie : 'ohne';
      return l === linieSchluessel;
    });
    if (!eigene.length) continue;

    eigene.sort((a, b) =>
      (bereiche[a.entity] || 'ÿ').localeCompare(bereiche[b.entity] || 'ÿ', 'de')
      || (a.name || '').localeCompare(b.name || '', 'de'));

    const sichtbar = eigene.filter((m) => !suche
      || `${m.name} ${m.entity} ${m.ort} ${bereiche[m.entity] || ''}`
        .toLowerCase().includes(suche));
    if (suche && !sichtbar.length) continue;

    const gruppe = el('details', 'karte gruppe');
    gruppe.open = true;
    const kopf = el('summary');
    const links = el('div');
    links.appendChild(el('strong', null, linie.name));
    const anzahl = eigene.filter((m) => m.aktiv !== false).length;
    links.appendChild(el('div', 'hilfe',
      anzahl === eigene.length
        ? `${eigene.length} Melder`
        : `${eigene.length} Melder, davon ${eigene.length - anzahl} abgeschaltet`));
    kopf.appendChild(links);
    kopf.appendChild(el('span', 'zahl', String(eigene.length)));
    gruppe.appendChild(kopf);

    const koerper = el('div', 'gruppe-koerper');
    const fehlend = fehlendeMelder(linieSchluessel);
    if (fehlend.length) koerper.appendChild(fehlHinweis(linieSchluessel, fehlend));

    for (const melder of sichtbar) {
      koerper.appendChild(melderKarte(melder, bereiche, zustaende,
        offen.has(melder.id)));
    }
    gruppe.appendChild(koerper);
    liste.appendChild(gruppe);
  }

  if (suche && !liste.hasChildNodes()) {
    liste.appendChild(el('div', 'leer', 'Kein Melder passt dazu.'));
  }
}

/* Was Home Assistant für diese Linie kennt, hier aber fehlt. */
function fehlendeMelder(linieSchluessel) {
  const arten = LINIENARTEN[linieSchluessel];
  if (!arten) return [];
  const drin = new Set((Z.konfig.melder || []).map((m) => m.entity));
  const weg = new Set(Z.auswahl?.ignoriert || []);
  return (Z.auswahl?.melder || []).filter((k) => arten.includes(k.art)
    && !drin.has(k.entity_id) && !weg.has(k.entity_id));
}

async function ignorieren(entity_id, an) {
  const antwort = await schicke('api/melder/ignorieren', { entity: entity_id, an });
  Z.auswahl.ignoriert = antwort.ignoriert;
  melderZeichnen(); vorschlaegeZeichnen();
}

function fehlHinweis(linieSchluessel, fehlend) {
  const kasten = el('div', 'fehlhinweis');
  const text = el('div');
  const arten = [...new Set(fehlend.map((f) =>
    (fehlend.length === 1 ? ARTEN[f.art] : ARTEN_MEHRZAHL[f.art]) || f.art))];
  text.appendChild(el('strong', null,
    `${fehlend.length} ${arten.join(' und ')} im Haus `
    + `${fehlend.length === 1 ? 'ist' : 'sind'} hier nicht eingerichtet`));
  text.appendChild(el('div', 'hilfe',
    fehlend.slice(0, 6).map((f) => f.name).join(', ')
    + (fehlend.length > 6 ? ` und ${fehlend.length - 6} weitere` : '')));
  kasten.appendChild(text);

  const knoepfe = el('div', 'zeile');
  knoepfe.style.margin = '0';

  const ansehen = el('button', 'knopf klein leise', 'Einzeln ansehen');
  ansehen.title = 'Öffnet die Liste – dort lässt sich auch ausblenden, was '
    + 'gar kein Melder ist.';
  ansehen.onclick = (ereignis) => {
    ereignis.preventDefault();
    const arten = LINIENARTEN[linieSchluessel] || [];
    $('melder-filter').value = arten.length === 1 ? arten[0] : '';
    $('melder-suche').value = '';
    $('melder-hinzufuegen').open = true;
    vorschlaegeZeichnen();
    $('melder-hinzufuegen').scrollIntoView({ block: 'start' });
  };
  knoepfe.appendChild(ansehen);

  const knopf = el('button', 'knopf klein', 'Alle hinzufügen');
  knopf.onclick = (ereignis) => {
    ereignis.preventDefault();
    for (const kandidat of fehlend) melderAnlegen(kandidat, linieSchluessel);
    melderSpeichern(); melderZeichnen(); vorschlaegeZeichnen();
    tost(`${fehlend.length} Melder hinzugefügt.`);
  };
  knoepfe.appendChild(knopf);
  kasten.appendChild(knoepfe);
  return kasten;
}

function melderAnlegen(kandidat, linieSchluessel) {
  const linie = linieSchluessel || (kandidat.art === 'rauch' ? 'rauch'
    : kandidat.art === 'wasser' ? 'wasser' : 'einbruch');
  Z.konfig.melder.push({
    entity: kandidat.entity_id,
    name: kandidat.name,
    ort: Z.auswahl?.bereiche?.[kandidat.entity_id] || kandidat.name,
    art: kandidat.art === 'sonstige' ? 'bewegung' : kandidat.art,
    linie,
    modi: [],
    verzoegert: Z.konfig.linien[linie]?.geltung === 'scharf',
    ausloesezustand: 'on',
    aktiv: true,
  });
}

/* Die Kurzfassung eines Melders – an genau einer Stelle gebaut.
 *
 * Sie stand einmal in zwei Funktionen, und prompt liefen sie auseinander:
 * "mit Ruhequelle · mit Ruhequelle". Ein Text, der zweimal gebaut wird,
 * wird irgendwann zweimal verschieden gebaut. */
function melderKurz(m) {
  const linie = Z.konfig.linien[m.linie];
  const teile = [ARTEN[m.art] || m.art];
  if (linie?.geltung === 'immer') {
    teile.push('rund um die Uhr');
  } else {
    teile.push(m.modi?.length
      ? m.modi.map((k) => Z.konfig.modi[k]?.name || k).join(', ')
      : 'alle Modi');
    teile.push(m.verzoegert !== false ? 'verzögert' : 'sofort');
  }
  if (m.mindestdauer) teile.push(`erst nach ${m.mindestdauer} s`);
  if (m.ruhe_bei?.length) teile.push('mit Ruhequelle');
  return teile.join(' · ');
}

function kurzAktualisieren(kopf, m) {
  kopf.querySelector('.melder-kurz').textContent = melderKurz(m);
}

/* Ein Melder als zugeklappte Zeile. Zugeklappt steht dort, was man beim
 * Durchsehen wissen will: wo er hängt, was er ist, wann er gilt.
 *
 * Aufgeklappt in drei Abschnitten. Ohne sie stehen zehn Felder in einem
 * Rutsch untereinander, und nichts sagt mehr, was zu was gehört. */
function melderKarte(m, bereiche, zustaende, war_offen) {
  const karte = el('details', 'melder' + (m.aktiv === false ? ' aus' : ''));
  karte.dataset.id = m.id;
  karte.open = !!war_offen;

  const kopf = el('summary', 'melder-kopf');
  const zustand = zustaende.get(m.entity);
  const punkt = el('span', 'melder-punkt'
    + (zustand === (m.ausloesezustand || 'on') ? ' an' : '')
    + (zustand === undefined ? ' fehlt' : ''));
  punkt.title = zustand === undefined ? 'Gibt es in Home Assistant nicht'
    : `Zustand gerade: ${zustand}`;
  kopf.appendChild(punkt);

  const mitte = el('div', 'melder-mitte');
  mitte.appendChild(el('div', 'melder-name', m.name || m.entity));
  mitte.appendChild(el('div', 'melder-kurz', melderKurz(m)));
  kopf.appendChild(mitte);

  const bereich = bereiche[m.entity];
  if (bereich) kopf.appendChild(el('span', 'kanal-bereich', bereich));
  if (m.aktiv === false) kopf.appendChild(el('span', 'marke warn', 'aus'));
  karte.appendChild(kopf);

  const koerper = el('div', 'melder-koerper');
  koerper.appendChild(el('div', 'kanal-eid', m.entity));

  const abschnitt = (titel) => {
    const kasten = el('div', 'melder-abschnitt');
    kasten.appendChild(el('h3', null, titel));
    koerper.appendChild(kasten);
    return kasten;
  };

  /* ------------------------------------------------------- Grundangaben */
  const grund = abschnitt('Was er ist');
  const felder = el('div', 'melder-felder');
  felder.appendChild(textfeld('Name', m.name, (wert) => {
    m.name = wert; melderSpeichern();
    kopf.querySelector('.melder-name').textContent = wert || m.entity;
  }));
  felder.appendChild(wahlfeld('Art', m.art, ARTEN, (wert) => {
    m.art = wert; melderSpeichern(); melderZeichnen();
  }));
  const linien = {};
  for (const [schluessel, l] of linienNachOrdnung()) linien[schluessel] = l.name;
  felder.appendChild(wahlfeld('Linie', m.linie, linien, (wert) => {
    m.linie = wert;
    /* Eine Dauerlinie kennt keine Eintrittsverzögerung – der Haken bliebe
     * sonst gesetzt und wirkungslos stehen. */
    m.verzoegert = Z.konfig.linien[wert]?.geltung === 'scharf';
    melderSpeichern(); melderZeichnen();
  }));
  felder.appendChild(textfeld('Ort (wird vorgelesen)', m.ort, (wert) => {
    m.ort = wert; melderSpeichern();
  }));
  felder.appendChild(textfeld('Löst aus bei', m.ausloesezustand || 'on', (wert) => {
    m.ausloesezustand = wert; melderSpeichern();
  }));
  grund.appendChild(felder);

  /* --------------------------------------------------------- Wann er zählt */
  const wann = abschnitt('Wann er zählt');
  const linie = Z.konfig.linien[m.linie];

  if (linie?.geltung === 'scharf') {
    const wahl = el('div', 'modiwahl');
    wahl.appendChild(el('span', 'modiwahl-titel', 'In diesen Modi:'));
    const modi = Object.entries(Z.konfig.modi).filter(([, x]) => x.aktiv);
    for (const [schluessel, modus] of modi) {
      const label = el('label');
      const kasten = el('input');
      kasten.type = 'checkbox';
      kasten.checked = !m.modi?.length || m.modi.includes(schluessel);
      kasten.onchange = () => {
        const alleModi = modi.map(([k]) => k);
        let gewaehlt = m.modi?.length ? [...m.modi] : [...alleModi];
        if (kasten.checked) gewaehlt.push(schluessel);
        else gewaehlt = gewaehlt.filter((k) => k !== schluessel);
        /* Alle angehakt = leere Liste. Das ist nicht Kosmetik: Kommt später
         * ein Modus dazu, gilt der Melder dann auch dort, statt
         * stillschweigend zu fehlen. */
        m.modi = gewaehlt.length === alleModi.length ? [] : gewaehlt;
        melderSpeichern(); kurzAktualisieren(kopf, m);
      };
      label.appendChild(kasten);
      label.appendChild(el('span', null, modus.name));
      wahl.appendChild(label);
    }
    wann.appendChild(wahl);

    const verz = el('label', 'kanal-an');
    const verzKasten = el('input');
    verzKasten.type = 'checkbox';
    verzKasten.checked = m.verzoegert !== false;
    verzKasten.onchange = () => {
      m.verzoegert = verzKasten.checked;
      melderSpeichern(); kurzAktualisieren(kopf, m);
    };
    verz.appendChild(verzKasten);
    const verzText = el('span');
    verzText.appendChild(el('strong', null, 'Eintrittsverzögerung'));
    verzText.appendChild(el('small', null,
      'Aus heißt: löst sofort aus, ohne Zeit zum Entschärfen.'));
    verz.appendChild(verzText);
    wann.appendChild(verz);
  } else {
    wann.appendChild(el('div', 'hilfe',
      'Diese Linie gilt rund um die Uhr – der Melder zählt immer, auch '
      + 'wenn die Anlage entschärft ist.'));
  }

  /* ------------------------------------------------------ Gegen Fehlalarme */
  const stoerung = abschnitt('Gegen Fehlalarme');
  const stoerfelder = el('div', 'melder-felder');

  const dauer = el('label');
  dauer.appendChild(document.createTextNode('Mindestdauer'));
  dauer.title = 'Vorsicht bei Präsenzmeldern: Viele halten von sich aus rund '
    + '60 Sekunden. Dort trennt die Mindestdauer echte von falschen '
    + 'Auslösungen nicht – beide sehen gleich lang aus.';
  const dauerZeile = el('span', 'einheit');
  const dauerFeld = el('input');
  dauerFeld.type = 'number';
  dauerFeld.min = '0';
  dauerFeld.value = m.mindestdauer || 0;
  dauerFeld.onchange = () => {
    m.mindestdauer = parseInt(dauerFeld.value, 10) || 0;
    melderSpeichern(); kurzAktualisieren(kopf, m);
  };
  dauerZeile.appendChild(dauerFeld);
  dauerZeile.appendChild(el('span', null, 'Sekunden anhalten'));
  dauer.appendChild(dauerZeile);
  stoerfelder.appendChild(dauer);
  stoerung.appendChild(stoerfelder);

  /* Die Ruhezeit gehört in die Ruhequelle, nicht daneben: Ohne Quelle ist
   * sie bedeutungslos, und als eigenes Feld sah sie aus wie eine zweite
   * Mindestdauer. */
  const ruheZeit = el('label', 'kanal-farbe');
  ruheZeit.appendChild(el('span', null, 'Danach übergehen für'));
  const ruheEinheit = el('span', 'einheit');
  const ruheFeld = el('input');
  ruheFeld.type = 'number';
  ruheFeld.min = '0';
  ruheFeld.value = m.ruhe_sekunden ?? 120;
  ruheFeld.onchange = () => {
    m.ruhe_sekunden = parseInt(ruheFeld.value, 10) || 0;
    melderSpeichern();
  };
  ruheEinheit.appendChild(ruheFeld);
  ruheEinheit.appendChild(el('span', null, 'Sekunden'));
  ruheZeit.appendChild(ruheEinheit);

  stoerung.appendChild(auswahlKarte({
    titel: 'Ruht, wenn sich das bewegt hat',
    alle: Z.auswahl?.bewegliches || [],
    gewaehlt: m.ruhe_bei || [],
    leerText: 'nichts – der Melder zählt immer',
    nachtrag: ruheZeit,
    beiAenderung: (auswahl) => {
      m.ruhe_bei = auswahl; melderSpeichern(); kurzAktualisieren(kopf, m);
    },
  }));
  stoerung.appendChild(el('div', 'hilfe',
    'Ein Präsenzmelder sieht den Rollladen im selben Zimmer fahren. Gegen '
    + 'so eine bekannte Ursache hilft kein Zeitfilter, sondern das Rollo '
    + 'als Ruhequelle.'));

  /* ------------------------------------------------------------- Meldung */
  const meldung = abschnitt('Was gemeldet wird');
  const eigenerText = el('label', 'melder-text');
  eigenerText.appendChild(document.createTextNode(
    'Eigener Meldetext (leer = der Satz der Linie)'));
  const textfeldEigen = el('input');
  textfeldEigen.type = 'text';
  textfeldEigen.placeholder = vorgabetext(m);
  textfeldEigen.value = m.text || '';
  textfeldEigen.oninput = () => { m.text = textfeldEigen.value; melderSpeichern(); };
  eigenerText.appendChild(textfeldEigen);
  eigenerText.appendChild(el('small', null,
    'Platzhalter: {ort} {zeit}. Gilt für den Alarm, nicht für die Entwarnung.'));
  meldung.appendChild(eigenerText);

  /* ---------------------------------------------------------------- Fuß */
  const fuss = el('div', 'melder-fuss');
  const an = el('label', 'kanal-an');
  const anKasten = el('input');
  anKasten.type = 'checkbox';
  anKasten.checked = m.aktiv !== false;
  anKasten.onchange = () => {
    m.aktiv = anKasten.checked; melderSpeichern(); melderZeichnen();
  };
  an.appendChild(anKasten);
  an.appendChild(el('span', null, 'Dieser Melder zählt'));
  fuss.appendChild(an);

  const weg = el('button', 'knopf klein leise', 'Entfernen');
  weg.onclick = (ereignis) => {
    ereignis.preventDefault();
    Z.konfig.melder = Z.konfig.melder.filter((x) => x.id !== m.id);
    melderSpeichern(); melderZeichnen(); vorschlaegeZeichnen();
  };
  fuss.appendChild(weg);
  koerper.appendChild(fuss);

  karte.appendChild(koerper);
  return karte;
}

/* Was ohne eigenen Text gesagt würde – als blasse Vorgabe im Feld, damit
 * sichtbar ist, wogegen man schreibt. */
function vorgabetext(m) {
  const stufe = Z.konfig.eskalation?.[m.linie]?.alarm;
  const vorlage = stufe?.text || {
    einbruch: 'Bewegung erkannt: {ausloeser}. Modus: {modus}.',
    rauch: 'Achtung! {ort} meldet Rauch.',
    wasser: 'Achtung! {ort} meldet Wasser.',
  }[m.linie] || '';
  return vorlage.replace('{ort}', m.ort || m.name || '')
    .replace('{ausloeser}', m.ort || m.name || '');
}

function textfeld(beschriftung, wert, beiAenderung) {
  const label = el('label');
  label.appendChild(document.createTextNode(beschriftung));
  const feld = el('input');
  feld.type = 'text';
  feld.value = wert || '';
  feld.oninput = () => beiAenderung(feld.value);
  label.appendChild(feld);
  return label;
}

function wahlfeld(beschriftung, wert, werte, beiAenderung) {
  const label = el('label');
  label.appendChild(document.createTextNode(beschriftung));
  const auswahl = el('select');
  for (const [schluessel, text] of Object.entries(werte)) {
    const option = el('option', null, text);
    option.value = schluessel;
    if (schluessel === wert) option.selected = true;
    auswahl.appendChild(option);
  }
  auswahl.onchange = () => beiAenderung(auswahl.value);
  label.appendChild(auswahl);
  return label;
}

let melderZeit = null;
function melderSpeichern() {
  clearTimeout(melderZeit);
  melderZeit = setTimeout(async () => {
    try {
      const antwort = await schicke('api/melder', Z.konfig.melder);
      Z.konfig.melder = antwort.melder;
      tost('Gespeichert');
    } catch (fehler) { tost('Nicht gespeichert: ' + fehler.message, true); }
  }, 400);
}

function standHinzufuegen() {
  const drin = new Set((Z.konfig.melder || []).map((m) => m.entity));
  const frei = (Z.auswahl?.melder || []).filter((k) => !drin.has(k.entity_id));
  const stand = $('hinzufuegen-stand');
  const zahl = $('hinzufuegen-zahl');
  if (!stand) return;
  const nuetzlich = frei.filter((k) => k.art !== 'sonstige');
  stand.textContent = nuetzlich.length
    ? `${nuetzlich.length} erkannte Melder sind noch nicht eingerichtet`
    : 'Alles Erkannte ist eingerichtet';
  zahl.textContent = `${frei.length} frei`;
}

function vorschlaegeZeichnen() {
  const kasten = $('melder-vorschlaege');
  kasten.textContent = '';
  const suche = $('melder-suche').value.toLowerCase();
  const filter = $('melder-filter').value;
  const drin = new Set((Z.konfig.melder || []).map((m) => m.entity));
  const bereiche = Z.auswahl?.bereiche || {};

  const weg = new Set(Z.auswahl?.ignoriert || []);
  const zeigeWeg = $('melder-ausgeblendet')?.checked;
  const sortiert = [...(Z.auswahl?.melder || [])].sort((a, b) => {
    const da = drin.has(a.entity_id) ? 1 : 0;
    const db = drin.has(b.entity_id) ? 1 : 0;
    if (da !== db) return da - db;
    const ia = ARTORDNUNG.indexOf(a.art);
    const ib = ARTORDNUNG.indexOf(b.art);
    if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    return (a.name || '').localeCompare(b.name || '', 'de');
  });

  ausgeblendetStand(weg.size);
  let gezeigt = 0;
  for (const kandidat of sortiert) {
    if (weg.has(kandidat.entity_id) !== !!zeigeWeg) continue;
    if (filter && kandidat.art !== filter) continue;
    const bereich = bereiche[kandidat.entity_id] || '';
    if (suche && !`${kandidat.name} ${kandidat.entity_id} ${bereich}`
      .toLowerCase().includes(suche)) continue;
    if (gezeigt++ > 300) break;

    const zeile = el('div',
      'vorschlagszeile' + (drin.has(kandidat.entity_id) ? ' drin' : ''));
    const links = el('div', 'kanal-text');
    links.appendChild(el('div', 'kanal-name', kandidat.name));
    links.appendChild(el('div', 'kanal-eid',
      `${kandidat.entity_id} · ${ARTEN[kandidat.art] || kandidat.art}`));
    zeile.appendChild(links);
    if (bereich) zeile.appendChild(el('span', 'kanal-bereich', bereich));

    const knopf = el('button', 'knopf klein',
      drin.has(kandidat.entity_id) ? 'schon drin' : 'Hinzufügen');
    knopf.disabled = drin.has(kandidat.entity_id);
    knopf.onclick = () => {
      melderAnlegen(kandidat);
      melderSpeichern(); melderZeichnen(); vorschlaegeZeichnen();
    };
    zeile.appendChild(knopf);

    /* Ausblenden ist kein Zierrat: "binary_sensor mit Geräteklasse door"
     * trifft in einer gewachsenen Installation auch auf Dinge zu, die mit
     * dem Haus nichts zu tun haben – etwa auf den Öffnungszustand von
     * Tankstellen. Wer die einmal wegräumt, will sie nie wiedersehen. */
    if (!drin.has(kandidat.entity_id)) {
      const weiter = el('button', 'kanal-weg',
        zeigeWeg ? '↩' : '✕');
      weiter.title = zeigeWeg ? 'Wieder anbieten'
        : 'Nicht mehr anbieten – das ist kein Melder';
      weiter.onclick = (ereignis) => {
        ereignis.preventDefault();
        ignorieren(kandidat.entity_id, !zeigeWeg);
      };
      zeile.appendChild(weiter);
    }
    kasten.appendChild(zeile);
  }
  if (!gezeigt) {
    kasten.appendChild(el('div', 'leer', zeigeWeg
      ? 'Nichts ausgeblendet.' : 'Nichts gefunden.'));
  }
}

function ausgeblendetStand(anzahl) {
  const zeile = $('melder-ausgeblendet-zeile');
  if (!zeile) return;
  zeile.style.display = anzahl ? '' : 'none';
  $('melder-ausgeblendet-zahl').textContent =
    `${anzahl} ausgeblendet anzeigen`;
}

$('melder-suche').oninput = vorschlaegeZeichnen;
$('melder-filtern').oninput = melderZeichnen;
$('melder-filter').onchange = vorschlaegeZeichnen;
$('melder-ausgeblendet').onchange = vorschlaegeZeichnen;

/* --------------------------------------------------------------- Modi */

function modiZeichnen() {
  const liste = $('modi-liste');
  liste.textContent = '';
  const eintraege = Object.entries(Z.konfig.modi)
    .sort((a, b) => (a[1].reihenfolge || 99) - (b[1].reihenfolge || 99));

  for (const [schluessel, modus] of eintraege) {
    const kasten = el('div', 'melder' + (modus.aktiv ? '' : ' aus'));
    const kopf = el('div', 'melder-kopf');
    const name = el('input', 'name');
    name.type = 'text';
    name.value = modus.name;
    name.oninput = () => {
      modus.name = name.value;
      konfigSpeichern({ modi: { [schluessel]: { name: name.value } } });
    };
    kopf.appendChild(name);
    const an = el('label');
    an.style.cssText = 'display:flex;gap:6px;color:var(--text)';
    const anKasten = el('input');
    anKasten.type = 'checkbox';
    anKasten.checked = !!modus.aktiv;
    anKasten.onchange = () => {
      modus.aktiv = anKasten.checked;
      konfigSpeichern({ modi: { [schluessel]: { aktiv: anKasten.checked } } });
      modiZeichnen(); melderZeichnen(); modusAuswahlenFuellen();
    };
    an.appendChild(anKasten);
    an.appendChild(el('span', null, 'in Benutzung'));
    kopf.appendChild(an);
    kopf.appendChild(el('div', 'eid',
      `Bedienfeld: ${PANELTEXT[modus.panel_zustand] || modus.panel_zustand}`));
    kasten.appendChild(kopf);

    const felder = el('div', 'melder-felder');
    felder.appendChild(zahlfeld('Ausgehverzögerung (s)', modus.ausgehzeit, (wert) => {
      modus.ausgehzeit = wert;
      konfigSpeichern({ modi: { [schluessel]: { ausgehzeit: wert } } });
    }));
    felder.appendChild(zahlfeld('Eintrittsverzögerung (s)', modus.eintrittszeit, (wert) => {
      modus.eintrittszeit = wert;
      konfigSpeichern({ modi: { [schluessel]: { eintrittszeit: wert } } });
    }));
    kasten.appendChild(felder);
    liste.appendChild(kasten);
  }
}

const linienNachOrdnung = () => Object.entries(Z.konfig.linien)
  .sort((a, b) => (a[1].reihenfolge || 99) - (b[1].reihenfolge || 99));

function linienZeichnen() {
  const liste = $('linien-liste');
  liste.textContent = '';
  for (const [schluessel, linie] of linienNachOrdnung()) {
    const kasten = el('div', 'melder' + (linie.aktiv ? '' : ' aus'));
    const kopf = el('div', 'melder-kopf');
    kopf.appendChild(el('div', 'name', linie.name));
    const an = el('label');
    an.style.cssText = 'display:flex;gap:6px;color:var(--text)';
    const anKasten = el('input');
    anKasten.type = 'checkbox';
    anKasten.checked = !!linie.aktiv;
    anKasten.onchange = () => {
      linie.aktiv = anKasten.checked;
      konfigSpeichern({ linien: { [schluessel]: { aktiv: anKasten.checked } } });
      linienZeichnen();
    };
    an.appendChild(anKasten);
    an.appendChild(el('span', null, 'in Benutzung'));
    kopf.appendChild(an);
    kasten.appendChild(kopf);

    const felder = el('div', 'melder-felder');
    felder.appendChild(wahlfeld('Geltung', linie.geltung,
      { scharf: 'nur wenn scharf', immer: 'rund um die Uhr' }, (wert) => {
        linie.geltung = wert;
        konfigSpeichern({ linien: { [schluessel]: { geltung: wert } } });
        melderZeichnen();
      }));
    if (linie.geltung === 'scharf') {
      felder.appendChild(zahlfeld('Auslösedauer (s, 0 = bis entschärft)',
        linie.ausloesezeit, (wert) => {
          linie.ausloesezeit = wert;
          konfigSpeichern({ linien: { [schluessel]: { ausloesezeit: wert } } });
        }));
    }
    kasten.appendChild(felder);
    liste.appendChild(kasten);
  }
}

function zahlfeld(beschriftung, wert, beiAenderung) {
  const label = el('label');
  label.appendChild(document.createTextNode(beschriftung));
  const feld = el('input');
  feld.type = 'number';
  feld.min = '0';
  feld.value = wert ?? 0;
  feld.onchange = () => beiAenderung(parseInt(feld.value, 10) || 0);
  label.appendChild(feld);
  return label;
}

/* ------------------------------------------------------ Scharfschaltung */

function schaltungZeichnen() {
  const s = Z.konfig.scharfschaltung;

  const quellen = {
    anwesenheit: ['Der Anwesenheit folgen',
      'Der Hausmodus wechselt, sobald jemand kommt oder alle weg sind.'],
    entitaet: ['Einer vorhandenen Entität folgen',
      'Etwa einem input_select, den andere Automationen schon setzen.'],
    nur_hand: ['Nur von Hand',
      'Die Anlage schaltet nie von selbst – nur über Bedienfeld oder Karte.'],
  };
  const wahl = $('quelle-wahl');
  wahl.textContent = '';
  for (const [schluessel, [titel, hilfe]] of Object.entries(quellen)) {
    const label = el('label', s.quelle === schluessel ? 'an' : '');
    const knopf = el('input');
    knopf.type = 'radio';
    knopf.name = 'quelle';
    knopf.checked = s.quelle === schluessel;
    knopf.onchange = () => {
      s.quelle = schluessel;
      konfigSpeichern({ scharfschaltung: { quelle: schluessel } });
      schaltungZeichnen();
    };
    label.appendChild(knopf);
    label.appendChild(document.createTextNode(titel));
    label.appendChild(el('small', null, hilfe));
    wahl.appendChild(label);
  }
  $('anwesenheit-block').className = s.quelle === 'anwesenheit' ? '' : 'versteckt';
  $('entitaet-block').className = s.quelle === 'entitaet' ? '' : 'versteckt';

  kaestchen($('personen-liste'), Z.auswahl?.personen || [], s.personen || [],
    (liste) => {
      s.personen = liste;
      konfigSpeichern({ scharfschaltung: { personen: liste } });
    });

  modusAuswahlenFuellen();
  $('leer-minuten').value = Math.round((s.leer_sekunden || 0) / 60);
  $('leer-minuten').onchange = (e) => {
    const wert = (parseInt(e.target.value, 10) || 0) * 60;
    s.leer_sekunden = wert;
    konfigSpeichern({ scharfschaltung: { leer_sekunden: wert } });
  };
  $('nie-scharf').checked = s.nie_scharf_wenn_jemand_da !== false;
  $('nie-scharf').onchange = (e) =>
    konfigSpeichern({ scharfschaltung: { nie_scharf_wenn_jemand_da: e.target.checked } });

  /* Entschärfung */
  const ent = Z.konfig.entschaerfung;
  kaestchen($('schloesser-liste'), Z.auswahl?.schloesser || [], ent.schloesser || [],
    (liste) => {
      ent.schloesser = liste;
      konfigSpeichern({ entschaerfung: { schloesser: liste } });
    });

  const zusatzWahl = $('zusatz-wahl');
  zusatzWahl.textContent = '';
  for (const eintrag of (Z.auswahl?.sensoren || []).slice(0, 2000)) {
    if ((ent.zusatzmelder || []).includes(eintrag.entity_id)) continue;
    const option = el('option', null, `${eintrag.name} (${eintrag.entity_id})`);
    option.value = eintrag.entity_id;
    zusatzWahl.appendChild(option);
  }
  $('zusatz-hinzu').onclick = () => {
    if (!zusatzWahl.value) return;
    ent.zusatzmelder = [...(ent.zusatzmelder || []), zusatzWahl.value];
    konfigSpeichern({ entschaerfung: { zusatzmelder: ent.zusatzmelder } });
    schaltungZeichnen();
  };
  chips($('zusatz-liste'), ent.zusatzmelder || [], (liste) => {
    ent.zusatzmelder = liste;
    konfigSpeichern({ entschaerfung: { zusatzmelder: liste } });
    schaltungZeichnen();
  });

  const zahlen = [
    ['nachlauf-minuten', 'nachlauf_minuten'],
    ['nachlauf-hoechstens', 'nachlauf_hoechstens_minuten'],
    ['wieder-scharf', 'wieder_scharf_minuten'],
    ['rueckfall', 'rueckfall_stunden'],
    ['meldung-abstand', 'meldung_abstand_minuten'],
  ];
  for (const [feldId, schluessel] of zahlen) {
    $(feldId).value = ent[schluessel] ?? 0;
    $(feldId).onchange = (e) => {
      const wert = parseInt(e.target.value, 10) || 0;
      ent[schluessel] = wert;
      konfigSpeichern({ entschaerfung: { [schluessel]: wert } });
    };
  }
  $('unterdrueckung-melden').checked = ent.melden !== false;
  $('unterdrueckung-melden').onchange = (e) =>
    konfigSpeichern({ entschaerfung: { melden: e.target.checked } });

  /* Vorprüfung */
  const arten = {
    melden: ['Melden und trotzdem scharf schalten',
      'Die Anlage schaltet, schreibt den offenen Kontakt aber ins Protokoll.'],
    ueberbruecken: ['Offene Kontakte überbrücken',
      'Der offene Kontakt zählt in diesem Durchgang nicht – der Rest schon.'],
    verhindern: ['Nicht scharf schalten',
      'Sicher, aber bei einem klemmenden Fenster steht die Anlage offen.'],
  };
  const vorWahl = $('vorpruefung-wahl');
  vorWahl.textContent = '';
  const jetzt = Z.konfig.vorpruefung?.offene_kontakte || 'melden';
  for (const [schluessel, [titel, hilfe]] of Object.entries(arten)) {
    const label = el('label', jetzt === schluessel ? 'an' : '');
    const knopf = el('input');
    knopf.type = 'radio';
    knopf.name = 'vorpruefung';
    knopf.checked = jetzt === schluessel;
    knopf.onchange = () => {
      konfigSpeichern({ vorpruefung: { offene_kontakte: schluessel } });
      schaltungZeichnen();
    };
    label.appendChild(knopf);
    label.appendChild(document.createTextNode(titel));
    label.appendChild(el('small', null, hilfe));
    vorWahl.appendChild(label);
  }
}

function modusAuswahlenFuellen() {
  const s = Z.konfig.scharfschaltung;
  const aktive = Object.entries(Z.konfig.modi).filter(([, m]) => m.aktiv);
  for (const [feldId, wert, mitLeer] of [
    ['modus-leer', s.modus_leer, false],
    ['handmodus', s.handmodus, true],
  ]) {
    const feld = $(feldId);
    if (!feld) continue;
    feld.textContent = '';
    if (mitLeer) {
      const leer = el('option', null, '– keiner –');
      leer.value = '';
      feld.appendChild(leer);
    }
    for (const [schluessel, modus] of aktive) {
      const option = el('option', null, modus.name);
      option.value = schluessel;
      if (schluessel === wert) option.selected = true;
      feld.appendChild(option);
    }
    feld.onchange = () => {
      const schluessel = feldId === 'modus-leer' ? 'modus_leer' : 'handmodus';
      s[schluessel] = feld.value;
      konfigSpeichern({ scharfschaltung: { [schluessel]: feld.value } });
    };
  }
}

function kaestchen(kasten, alle, gewaehlt, beiAenderung) {
  kasten.textContent = '';
  /* Die Klasse wird hier gesetzt, nicht vom Aufrufer erwartet: Die Hälfte
     dieser Listen entsteht zur Laufzeit, und ohne sie steht jeder Name
     unter statt neben seinem Kästchen. */
  kasten.classList.add('kaestchenliste');
  const drin = new Set(gewaehlt);
  /* Auch das Gewählte zeigen, wenn die Entität gerade fehlt – sonst
   * verschwindet eine Zuordnung stillschweigend, weil ein Gerät
   * kurzzeitig nicht da ist. */
  const liste = [...alle];
  for (const entity_id of gewaehlt) {
    if (!alle.some((e) => e.entity_id === entity_id)) {
      liste.push({ entity_id, name: entity_id + ' (fehlt gerade)' });
    }
  }
  for (const eintrag of liste) {
    const label = el('label');
    const knopf = el('input');
    knopf.type = 'checkbox';
    knopf.checked = drin.has(eintrag.entity_id);
    knopf.onchange = () => {
      if (knopf.checked) drin.add(eintrag.entity_id);
      else drin.delete(eintrag.entity_id);
      beiAenderung([...drin]);
    };
    label.appendChild(knopf);
    const text = el('span');
    text.appendChild(document.createTextNode(eintrag.name));
    text.appendChild(el('div', 'eid', eintrag.entity_id));
    label.appendChild(text);
    kasten.appendChild(label);
  }
  if (!liste.length) kasten.appendChild(el('div', 'leer', 'Nichts gefunden.'));
}

function chips(kasten, liste, beiAenderung) {
  kasten.textContent = '';
  liste.forEach((eintrag, index) => {
    const chip = el('span', 'chip');
    chip.appendChild(document.createTextNode(eintrag));
    const weg = el('button', null, '×');
    weg.title = 'Entfernen';
    weg.onclick = () => beiAenderung(liste.filter((_, i) => i !== index));
    chip.appendChild(weg);
    kasten.appendChild(chip);
  });
}

/* ---------------------------------------------------------- Meldewege */

/* Der Filter im Protokoll soll dieselben Wörter anbieten, die in den
 * Einträgen stehen – sonst sucht man nach "Ruhequelle" und findet nichts. */
function protokollfilterFuellen() {
  const feld = $('protokoll-filter');
  if (!feld || feld.dataset.gefuellt) return;
  feld.dataset.gefuellt = '1';
  const behalten = feld.value;
  feld.textContent = '';
  const leer = el('option', null, 'alles');
  leer.value = '';
  feld.appendChild(leer);
  for (const [schluessel, text] of Object.entries(PROTOKOLLTEXT)) {
    const option = el('option', null, text);
    option.value = schluessel;
    feld.appendChild(option);
  }
  feld.value = behalten;
}

const STUFENTEXT = {
  voralarm: ['Voralarm', 'Während der Eintrittsverzögerung, bevor der Alarm '
    + 'losgeht. Wer in dieser Zeit entschärft, soll nicht geweckt werden – '
    + 'deshalb ist die Stufe im Regelfall aus.'],
  alarm: ['Alarm', 'Der Ernstfall.'],
  entwarnung: ['Entwarnung', 'Nach dem Entschärfen. Ohne sie bleibt nach dem '
    + 'Push offen, ob jemand reagiert hat oder ob die Meldung ausgelaufen ist.'],
};

/* Die Reihenfolge der Stufen steht hier und nirgends sonst.
 *
 * Sie aus der Schlüsselfolge des JSON zu lesen, ging schief: Flask sortiert
 * die Schlüssel alphabetisch, und damit stand der Voralarm plötzlich hinter
 * der Entwarnung - also hinter dem, was er ankündigt. Reihenfolge ist eine
 * Aussage und gehört ausgeschrieben. */
const STUFEN_ORDNUNG = ['voralarm', 'alarm', 'entwarnung'];

const nachOrdnung = (liste, ordnung) => liste.sort((a, b) => {
  const ia = ordnung.indexOf(a[0]);
  const ib = ordnung.indexOf(b[0]);
  return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
});

/* Ab wie vielen Einträgen eine Suche eingeblendet wird. Bei sieben
 * Telefonen braucht es keine; bei hundertfünfzig Lampen ist die Liste ohne
 * sie unbrauchbar. */
const SUCHE_AB = 10;

function meldewegeZeichnen() {
  const liste = $('meldewege-liste');
  liste.textContent = '';
  for (const [linieSchluessel, linie] of linienNachOrdnung()) {
    if (!linie.aktiv) continue;
    const karte = el('div', 'karte');
    karte.appendChild(el('h2', null, linie.name));
    const stufen = Z.konfig.eskalation[linieSchluessel] || {};
    for (const [stufeSchluessel, stufe] of
      nachOrdnung(Object.entries(stufen), STUFEN_ORDNUNG)) {
      karte.appendChild(stufeZeichnen(linieSchluessel, stufeSchluessel, stufe));
    }
    liste.appendChild(karte);
  }
}

/* Eine Auswahl aus vielen Einträgen als eigene, zugeklappte Karte.
 *
 * Zugeklappt steht dort, was gewählt ist – das ist die Frage, die man beim
 * Draufsehen hat. Die vollständige Liste kommt erst auf Verlangen, mit
 * Suche und dem Gewählten obenan. Vorher standen hier hundertfünfzig
 * Lampen am Stück, und die zwei angehakten lagen irgendwo dazwischen. */
function auswahlKarte(einstellungen) {
  const { titel, alle, gewaehlt, beiAenderung, leerText, nachtrag } = einstellungen;
  const drin = new Set(gewaehlt || []);

  const karte = el('details', 'kanal');
  const kopf = el('summary', 'kanal-kopf');
  const links = el('div', 'kanal-titel');
  links.appendChild(el('strong', null, titel));
  const stand = el('div', 'kanal-stand');
  links.appendChild(stand);
  kopf.appendChild(links);
  const zahl = el('span', 'kanal-zahl');
  kopf.appendChild(zahl);
  karte.appendChild(kopf);

  const koerper = el('div', 'kanal-koerper');
  karte.appendChild(koerper);

  /* Die Einträge, die es gar nicht (mehr) gibt, müssen trotzdem auftauchen:
   * Sonst verschwindet eine Zuordnung stillschweigend, weil ein Gerät
   * gerade nicht erreichbar ist. */
  const vollstaendig = [...(alle || [])];
  for (const id of drin) {
    if (!vollstaendig.some((e) => e.entity_id === id)) {
      vollstaendig.push({ entity_id: id, name: id, fehlt: true });
    }
  }

  const namen = new Map(vollstaendig.map((e) => [e.entity_id, e.name]));

  function standZeichnen() {
    zahl.textContent = drin.size ? `${drin.size} von ${vollstaendig.length}`
      : 'keine';
    zahl.className = 'kanal-zahl' + (drin.size ? ' an' : '');
    if (!drin.size) {
      stand.textContent = leerText || 'nichts ausgewählt';
      stand.classList.add('leise');
      return;
    }
    stand.classList.remove('leise');
    const gezeigt = [...drin].slice(0, 3).map((id) => namen.get(id) || id);
    stand.textContent = gezeigt.join(', ')
      + (drin.size > 3 ? ` und ${drin.size - 3} weitere` : '');
  }

  const suchfeld = el('input', 'kanal-suche');
  suchfeld.type = 'search';
  suchfeld.placeholder = 'Suchen …';
  if (vollstaendig.length >= SUCHE_AB) koerper.appendChild(suchfeld);

  const listenkasten = el('div', 'kanal-liste');
  koerper.appendChild(listenkasten);

  function listeZeichnen() {
    const suche = suchfeld.value.trim().toLowerCase();
    /* Sortiert wird nur beim Neuzeichnen, nicht bei jedem Haken: Sonst
     * springt der eben angeklickte Eintrag unter der Maus weg. */
    const sortiert = [...vollstaendig].sort((a, b) => {
      const da = drin.has(a.entity_id) ? 0 : 1;
      const db = drin.has(b.entity_id) ? 0 : 1;
      if (da !== db) return da - db;
      return (a.name || '').localeCompare(b.name || '', 'de');
    });

    listenkasten.textContent = '';
    let gezeigt = 0;
    for (const eintrag of sortiert) {
      const bereich = Z.auswahl?.bereiche?.[eintrag.entity_id] || '';
      if (suche && !`${eintrag.name} ${eintrag.entity_id} ${bereich}`
        .toLowerCase().includes(suche)) continue;
      gezeigt++;

      const label = el('label', 'kanal-zeile');
      const kasten = el('input');
      kasten.type = 'checkbox';
      kasten.checked = drin.has(eintrag.entity_id);
      kasten.onchange = () => {
        if (kasten.checked) drin.add(eintrag.entity_id);
        else drin.delete(eintrag.entity_id);
        label.classList.toggle('an', kasten.checked);
        standZeichnen();
        beiAenderung([...drin]);
      };
      label.classList.toggle('an', kasten.checked);
      label.appendChild(kasten);

      const text = el('div', 'kanal-text');
      text.appendChild(el('div', 'kanal-name',
        eintrag.name + (eintrag.fehlt ? ' (fehlt gerade)' : '')));
      const unten = el('div', 'kanal-eid', eintrag.entity_id);
      text.appendChild(unten);
      label.appendChild(text);

      if (bereich) label.appendChild(el('span', 'kanal-bereich', bereich));
      listenkasten.appendChild(label);
    }
    if (!gezeigt) listenkasten.appendChild(el('div', 'leer', 'Nichts gefunden.'));
  }

  suchfeld.oninput = listeZeichnen;
  /* Erst zeichnen, wenn jemand aufklappt. Bei vier Kanälen mal drei Stufen
   * mal drei Linien wären das sonst ein paar tausend Kästchen beim Laden. */
  karte.addEventListener('toggle', () => {
    if (karte.open && !listenkasten.hasChildNodes()) listeZeichnen();
  });

  if (nachtrag) koerper.appendChild(nachtrag);
  standZeichnen();
  return karte;
}

function stufeZeichnen(linieSchluessel, stufeSchluessel, stufe) {
  const [titel, hilfe] = STUFENTEXT[stufeSchluessel] || [stufeSchluessel, ''];
  const kasten = el('details', 'stufe');
  kasten.open = stufeSchluessel === 'alarm';

  const kopf = el('summary', 'stufe-kopf');
  const links = el('div');
  const zeile = el('div', 'stufe-name');
  zeile.appendChild(el('strong', null, titel));
  const marke = el('span', 'marke ' + (stufe.aktiv !== false ? 'gut' : ''));
  marke.textContent = stufe.aktiv !== false ? 'aktiv' : 'aus';
  zeile.appendChild(marke);
  if (stufe.kritisch) zeile.appendChild(el('span', 'marke warn', 'kritisch'));
  links.appendChild(zeile);
  links.appendChild(el('div', 'hilfe', hilfe));
  kopf.appendChild(links);
  kasten.appendChild(kopf);

  const koerper = el('div', 'stufe-koerper');

  const werkzeuge = el('div', 'zeile');
  const an = el('label', 'kanal-an');
  const anKasten = el('input');
  anKasten.type = 'checkbox';
  anKasten.checked = stufe.aktiv !== false;
  anKasten.onchange = () => {
    aendern(linieSchluessel, stufeSchluessel, { aktiv: anKasten.checked });
    marke.textContent = anKasten.checked ? 'aktiv' : 'aus';
    marke.className = 'marke ' + (anKasten.checked ? 'gut' : '');
  };
  an.appendChild(anKasten);
  an.appendChild(el('span', null, 'Diese Stufe meldet'));
  werkzeuge.appendChild(an);

  const probe = el('button', 'knopf klein leise', 'Einmal auslösen');
  probe.title = 'Schickt diese Stufe jetzt ab – so lässt sich prüfen, ob der '
    + 'kritische Push wirklich durch den Fokusmodus kommt.';
  probe.onclick = async (ereignis) => {
    ereignis.preventDefault();
    const antwort = await schicke('api/probe',
      { linie: linieSchluessel, stufe: stufeSchluessel });
    tost(antwort.getan?.unterdrueckt
      ? 'Trockenlauf – es ging nichts hinaus.'
      : `Abgeschickt: ${antwort.getan.push.length} Push, `
        + `${antwort.getan.sprache.length} Ansagen.`);
  };
  werkzeuge.appendChild(probe);
  koerper.appendChild(werkzeuge);

  const kanaele = el('div', 'kanaele');

  /* Push – mit dem kritischen Schalter darin, weil er nur dort gilt. */
  const kritisch = el('label', 'kanal-an abgesetzt');
  const kritischKasten = el('input');
  kritischKasten.type = 'checkbox';
  kritischKasten.checked = !!stufe.kritisch;
  kritischKasten.onchange = () => {
    aendern(linieSchluessel, stufeSchluessel, { kritisch: kritischKasten.checked });
    meldewegeZeichnen();
  };
  kritisch.appendChild(kritischKasten);
  const kritischText = el('span');
  kritischText.appendChild(el('strong', null, 'Kritischer Push'));
  kritischText.appendChild(el('small', null,
    'Durchbricht den Fokusmodus. Für den Ernstfall gedacht, nicht für Hinweise.'));
  kritisch.appendChild(kritischText);

  kanaele.appendChild(auswahlKarte({
    titel: 'Push aufs Telefon',
    alle: (Z.auswahl?.meldewege?.push || []).map((d) =>
      ({ entity_id: d.dienst, name: d.name })),
    gewaehlt: stufe.push || [],
    leerText: 'niemand bekommt einen Push',
    nachtrag: kritisch,
    beiAenderung: (auswahl) =>
      aendern(linieSchluessel, stufeSchluessel, { push: auswahl }),
  }));

  kanaele.appendChild(auswahlKarte({
    titel: 'Ansage über Lautsprecher',
    alle: (Z.auswahl?.meldewege?.sprache || []).map((d) =>
      ({ entity_id: d.dienst, name: d.name })),
    gewaehlt: stufe.alexa || [],
    leerText: 'keine Ansage',
    beiAenderung: (auswahl) =>
      aendern(linieSchluessel, stufeSchluessel, { alexa: auswahl }),
  }));

  const farbe = el('label', 'kanal-farbe');
  farbe.appendChild(el('span', null, 'Farbe, solange die Stufe läuft'));
  const farbfeld = el('input');
  farbfeld.type = 'color';
  farbfeld.value = rgbZuHex(stufe.licht_farbe || [255, 0, 0]);
  farbfeld.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { licht_farbe: hexZuRgb(farbfeld.value) });
  farbe.appendChild(farbfeld);

  kanaele.appendChild(auswahlKarte({
    titel: 'Licht',
    alle: Z.auswahl?.lichter || [],
    gewaehlt: stufe.licht || [],
    leerText: 'kein Licht',
    nachtrag: farbe,
    beiAenderung: (auswahl) =>
      aendern(linieSchluessel, stufeSchluessel, { licht: auswahl }),
  }));

  kanaele.appendChild(auswahlKarte({
    titel: 'Sirene oder Steckdose',
    alle: Z.auswahl?.schalter || [],
    gewaehlt: stufe.schalter || [],
    leerText: 'nichts wird geschaltet',
    beiAenderung: (auswahl) =>
      aendern(linieSchluessel, stufeSchluessel, { schalter: auswahl }),
  }));

  koerper.appendChild(kanaele);

  /* Text und Meldung in Home Assistant – gehören zur Stufe, nicht zu einem
   * Kanal. */
  const feinheiten = el('div', 'stufe-feinheiten');
  const text = el('label');
  text.appendChild(document.createTextNode(
    'Eigener Text (leer = vorgegebener Satz). Platzhalter: {ausloeser} {ort} '
    + '{modus} {rest} {zeit}'));
  const textfeld = el('input');
  textfeld.type = 'text';
  textfeld.value = stufe.text || '';
  textfeld.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { text: textfeld.value });
  text.appendChild(textfeld);
  feinheiten.appendChild(text);

  const persistent = el('label', 'kanal-an');
  const persistentKasten = el('input');
  persistentKasten.type = 'checkbox';
  persistentKasten.checked = stufe.persistent !== false;
  persistentKasten.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { persistent: persistentKasten.checked });
  persistent.appendChild(persistentKasten);
  const pText = el('span');
  pText.appendChild(el('strong', null, 'Meldung in Home Assistant hinterlassen'));
  pText.appendChild(el('small', null,
    'Bleibt stehen, bis jemand sie wegklickt – auch wenn der Push übersehen wurde.'));
  persistent.appendChild(pText);
  feinheiten.appendChild(persistent);

  koerper.appendChild(feinheiten);
  kasten.appendChild(koerper);
  return kasten;
}

function aendern(linie, stufe, teil) {
  Object.assign(Z.konfig.eskalation[linie][stufe], teil);
  konfigSpeichern({ eskalation: { [linie]: { [stufe]: teil } } });
}

const rgbZuHex = (rgb) => '#' + rgb.map((n) =>
  Math.max(0, Math.min(255, n)).toString(16).padStart(2, '0')).join('');
const hexZuRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.substr(i, 2), 16));

/* ---------------------------------------------------------- Übernahme */

$('vorschlag-laden').onclick = async () => {
  const kasten = $('uebernahme-ergebnis');
  kasten.textContent = '';
  kasten.appendChild(el('div', 'leer', 'Wird durchgesehen …'));
  try {
    const vorschlag = await hole('api/uebernahme/vorschlag');
    uebernahmeZeichnen(vorschlag);
  } catch (fehler) {
    kasten.textContent = '';
    kasten.appendChild(el('div', 'leer', 'Nicht lesbar: ' + fehler.message));
  }
};

function uebernahmeZeichnen(vorschlag) {
  const kasten = $('uebernahme-ergebnis');
  kasten.textContent = '';

  if (!vorschlag.automationen.length) {
    kasten.appendChild(el('div', 'leer',
      'Keine Automationen gefunden, die zur Alarmanlage gehören.'));
    return;
  }

  const gewaehlt = new Set(vorschlag.automationen
    .filter((a) => a.vorschlagen).map((a) => a.alias));

  const liste = el('div');
  liste.style.marginBottom = '14px';
  for (const automation of vorschlag.automationen) {
    const zeile = el('div', 'vorschlagszeile');
    const links = el('label');
    links.style.cssText = 'display:flex;gap:10px;align-items:flex-start;color:var(--text)';
    const knopf = el('input');
    knopf.type = 'checkbox';
    knopf.checked = gewaehlt.has(automation.alias);
    knopf.onchange = () => {
      if (knopf.checked) gewaehlt.add(automation.alias);
      else gewaehlt.delete(automation.alias);
    };
    links.appendChild(knopf);
    const text = el('div');
    text.appendChild(el('div', null, automation.alias));
    const unter = [`Linie: ${LINIENTEXT[automation.art] || automation.art}`,
      `${automation.entitaeten.length} Entitäten`];
    if (automation.aktiv === false) unter.push('steht schon auf aus');
    if (automation.fremdwirkung) {
      unter.push('greift außerdem an Rollos oder Licht ein – '
        + 'gehört vermutlich woandershin');
    }
    text.appendChild(el('div', 'eid', unter.join(' · ')));
    links.appendChild(text);
    zeile.appendChild(links);
    liste.appendChild(zeile);
  }
  kasten.appendChild(liste);

  const k = vorschlag.konfig;
  const zusammen = el('div', 'karte');
  zusammen.style.background = 'var(--flaeche2)';
  zusammen.appendChild(el('h2', null, 'Daraus würde'));
  zusammen.appendChild(el('div', null,
    `${k.melder.length} Melder · ${k.scharfschaltung.personen.length} Personen · `
    + `${k.entschaerfung.schloesser.length} Schlösser · `
    + `${(k.eskalation.einbruch.alarm.push || []).length} Push-Ziele · `
    + `${(k.eskalation.rauch.alarm.alexa || []).length} Lautsprecher`));
  const zeiten = Object.entries(k.modi).filter(([, m]) => m.aktiv)
    .map(([, m]) => `${m.name}: ${m.ausgehzeit} s hinaus, ${m.eintrittszeit} s herein`);
  zusammen.appendChild(el('div', 'eid', zeiten.join(' · ')));
  kasten.appendChild(zusammen);

  const knoepfe = el('div', 'zeile');

  const uebernehmen = el('button', 'knopf', 'Übernehmen');
  uebernehmen.onclick = async () => {
    await schicke('api/uebernahme', k);
    await allesLaden();
    tost('Übernommen. Die Anlage läuft im Trockenlauf – prüfen, dann '
      + 'unter Übersicht scharf schalten.');
    melderZeichnen(); modiZeichnen(); schaltungZeichnen(); meldewegeZeichnen();
  };
  knoepfe.appendChild(uebernehmen);

  const abschalten = el('button', 'knopf gefahr', 'Alte Automationen abschalten');
  abschalten.onclick = async () => {
    if (!confirm('Die ausgewählten Automationen werden ausgeschaltet '
      + '(nicht gelöscht). Der Zustand wird vorher gesichert.\n\n'
      + 'Vorher prüfen: Läuft die Anlage hier richtig? Ist der Trockenlauf aus?'))
      return;
    const antwort = await schicke('api/uebernahme/abschalten',
      { aliasse: [...gewaehlt] });
    tost(`${antwort.abgeschaltet.length} Automationen abgeschaltet.`);
    $('vorschlag-laden').click();
  };
  knoepfe.appendChild(abschalten);

  const zurueck = el('button', 'knopf leise', 'Wieder einschalten');
  zurueck.title = 'Stellt die jüngste Sicherung wieder her und schaltet den '
    + 'Trockenlauf ein.';
  zurueck.onclick = async () => {
    const antwort = await schicke('api/uebernahme/zurueck', {});
    tost(antwort.ok
      ? `${antwort.eingeschaltet.length} Automationen wieder an, Trockenlauf an.`
      : 'Keine Sicherung gefunden.', !antwort.ok);
    allesLaden();
  };
  knoepfe.appendChild(zurueck);

  kasten.appendChild(knoepfe);
}

/* ---------------------------------------------------------- Protokoll */

async function protokollLaden() {
  const liste = $('protokoll-liste');
  try {
    const art = $('protokoll-filter').value;
    const eintraege = await hole('api/protokoll?anzahl=300'
      + (art ? '&art=' + encodeURIComponent(art) : ''));
    liste.textContent = '';
    if (!eintraege.length) {
      liste.appendChild(el('div', 'leer', 'Noch nichts.'));
      return;
    }
    for (const eintrag of eintraege) {
      const zeile = el('div', 'p-zeile');
      zeile.appendChild(el('div', 'p-zeit',
        new Date(eintrag.zeit * 1000).toLocaleString('de-DE',
          { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })));
      zeile.appendChild(el('div', 'p-art ' + eintrag.art,
        PROTOKOLLTEXT[eintrag.art] || eintrag.art));
      zeile.appendChild(el('div', 'p-text', eintrag.text));
      liste.appendChild(zeile);
    }
  } catch (fehler) {
    liste.textContent = '';
    liste.appendChild(el('div', 'leer', 'Nicht lesbar: ' + fehler.message));
  }
}

$('protokoll-neu').onclick = protokollLaden;
$('protokoll-filter').onchange = protokollLaden;

/* ---------------------------------------------------------------- Lauf */

async function statusLaden() {
  try {
    Z.status = await hole('api/status');
    uebersichtZeichnen();
  } catch (fehler) {
    $('kopf-unter').textContent = 'Keine Verbindung zum Add-on';
  }
}

async function allesLaden() {
  const [konfig, auswahl] = await Promise.all([
    hole('api/konfig'),
    hole('api/auswahl'),
  ]);
  Z.konfig = konfig;
  Z.auswahl = auswahl;
  await statusLaden();
}

/* Der Reiter darf in der Adresse stehen (#melder). Praktisch beim
 * Verlinken aus der Dokumentation heraus - und beim Bebildern. */
function reiterAusAdresse() {
  const gewuenscht = (location.hash || '').replace('#', '');
  if (!gewuenscht) return;
  const knopf = document.querySelector(`[data-seite="${gewuenscht}"]`);
  if (knopf) knopf.click();
}
window.addEventListener('hashchange', reiterAusAdresse);

(async () => {
  try {
    await allesLaden();
    melderZeichnen();
    vorschlaegeZeichnen();
    modiZeichnen();
    linienZeichnen();
    schaltungZeichnen();
    meldewegeZeichnen();
    reiterAusAdresse();
  } catch (fehler) {
    tost('Start fehlgeschlagen: ' + fehler.message, true);
  }
  /* Eine Sekunde, weil Ausgeh- und Eintrittsverzögerung sekundenweise
   * herunterzählen – bei einer laufenden Frist will man zusehen können. */
  Z.ticker = setInterval(statusLaden, 1000);
})();
