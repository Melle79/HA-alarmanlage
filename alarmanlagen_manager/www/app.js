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
  if (Z.seite === 'protokoll') protokollLaden();
});

/* ---------------------------------------------------------- Übersicht */

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

function melderZeichnen() {
  const liste = $('melder-liste');
  liste.textContent = '';
  const melder = Z.konfig.melder || [];
  $('melder-zahl').textContent = melder.length;

  if (!melder.length) {
    liste.appendChild(el('div', 'leer',
      'Noch keiner. Oben auswählen – oder unter „Übernahme“ aus den '
      + 'vorhandenen Automationen holen.'));
  }

  const modi = Object.entries(Z.konfig.modi).filter(([, m]) => m.aktiv);

  melder.forEach((m, index) => {
    const kasten = el('div', 'melder' + (m.aktiv === false ? ' aus' : ''));

    const kopf = el('div', 'melder-kopf');
    const name = el('input', 'name');
    name.type = 'text';
    name.value = m.name || '';
    name.oninput = () => { m.name = name.value; melderSpeichern(); };
    kopf.appendChild(name);

    const an = el('label');
    an.style.display = 'flex';
    an.style.gap = '6px';
    an.style.color = 'var(--text)';
    const anKasten = el('input');
    anKasten.type = 'checkbox';
    anKasten.checked = m.aktiv !== false;
    anKasten.onchange = () => { m.aktiv = anKasten.checked; melderSpeichern(); melderZeichnen(); };
    an.appendChild(anKasten);
    an.appendChild(el('span', null, 'aktiv'));
    kopf.appendChild(an);

    const weg = el('button', 'knopf klein leise', 'Entfernen');
    weg.onclick = () => {
      Z.konfig.melder.splice(index, 1);
      melderSpeichern(); melderZeichnen(); vorschlaegeZeichnen();
    };
    kopf.appendChild(weg);
    kopf.appendChild(el('div', 'eid', m.entity));
    kasten.appendChild(kopf);

    const felder = el('div', 'melder-felder');

    felder.appendChild(wahlfeld('Art', m.art, ARTEN, (wert) => {
      m.art = wert; melderSpeichern();
    }));

    const linien = {};
    for (const [schluessel, linie] of Object.entries(Z.konfig.linien)) {
      linien[schluessel] = linie.name;
    }
    felder.appendChild(wahlfeld('Linie', m.linie, linien, (wert) => {
      m.linie = wert; melderSpeichern(); melderZeichnen();
    }));

    const ort = el('label');
    ort.appendChild(document.createTextNode('Ort (für die Ansage)'));
    const ortFeld = el('input');
    ortFeld.type = 'text';
    ortFeld.value = m.ort || '';
    ortFeld.oninput = () => { m.ort = ortFeld.value; melderSpeichern(); };
    ort.appendChild(ortFeld);
    felder.appendChild(ort);

    const zustand = el('label');
    zustand.appendChild(document.createTextNode('Löst aus bei'));
    const zustandFeld = el('input');
    zustandFeld.type = 'text';
    zustandFeld.value = m.ausloesezustand || 'on';
    zustandFeld.oninput = () => { m.ausloesezustand = zustandFeld.value; melderSpeichern(); };
    zustand.appendChild(zustandFeld);
    felder.appendChild(zustand);

    kasten.appendChild(felder);

    const istScharflinie = (Z.konfig.linien[m.linie] || {}).geltung === 'scharf';
    if (istScharflinie) {
      const wahl = el('div', 'modiwahl');
      wahl.appendChild(el('span', null, 'Gilt in:'));
      for (const [schluessel, modus] of modi) {
        const label = el('label');
        const kasten2 = el('input');
        kasten2.type = 'checkbox';
        kasten2.checked = !m.modi?.length || m.modi.includes(schluessel);
        kasten2.onchange = () => {
          const alle = modi.map(([s]) => s);
          let gewaehlt = m.modi?.length ? [...m.modi] : [...alle];
          if (kasten2.checked) gewaehlt.push(schluessel);
          else gewaehlt = gewaehlt.filter((s) => s !== schluessel);
          /* Alle angehakt = leere Liste. Das ist nicht Kosmetik: Kommt
           * später ein Modus dazu, gilt der Melder dann auch dort, statt
           * stillschweigend zu fehlen. */
          m.modi = gewaehlt.length === alle.length ? [] : gewaehlt;
          melderSpeichern();
        };
        label.appendChild(kasten2);
        label.appendChild(el('span', null, modus.name));
        wahl.appendChild(label);
      }

      const verz = el('label', 'abgesetzt');
      const verzKasten = el('input');
      verzKasten.type = 'checkbox';
      verzKasten.checked = m.verzoegert !== false;
      verzKasten.onchange = () => { m.verzoegert = verzKasten.checked; melderSpeichern(); };
      verz.appendChild(verzKasten);
      verz.appendChild(el('span', null, 'Eintrittsverzögerung'));
      verz.title = 'Aus heißt: löst sofort aus, ohne Zeit zum Entschärfen.';
      wahl.appendChild(verz);

      kasten.appendChild(wahl);
    }

    liste.appendChild(kasten);
  });
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

function vorschlaegeZeichnen() {
  const kasten = $('melder-vorschlaege');
  kasten.textContent = '';
  const suche = $('melder-suche').value.toLowerCase();
  const filter = $('melder-filter').value;
  const drin = new Set((Z.konfig.melder || []).map((m) => m.entity));
  const bereiche = Z.auswahl?.bereiche || {};

  let gezeigt = 0;
  for (const kandidat of Z.auswahl?.melder || []) {
    if (filter && kandidat.art !== filter) continue;
    if (suche && !(`${kandidat.name} ${kandidat.entity_id}`.toLowerCase().includes(suche))) continue;
    if (gezeigt++ > 200) break;

    const zeile = el('div', 'vorschlagszeile' + (drin.has(kandidat.entity_id) ? ' drin' : ''));
    const links = el('div');
    links.appendChild(el('div', null, kandidat.name));
    links.appendChild(el('div', 'eid',
      `${kandidat.entity_id} · ${ARTEN[kandidat.art] || kandidat.art}`
      + (bereiche[kandidat.entity_id] ? ' · ' + bereiche[kandidat.entity_id] : '')));
    zeile.appendChild(links);

    const knopf = el('button', 'knopf klein',
      drin.has(kandidat.entity_id) ? 'schon drin' : 'Hinzufügen');
    knopf.disabled = drin.has(kandidat.entity_id);
    knopf.onclick = () => {
      const linie = kandidat.art === 'rauch' ? 'rauch'
        : kandidat.art === 'wasser' ? 'wasser' : 'einbruch';
      Z.konfig.melder.push({
        entity: kandidat.entity_id,
        name: kandidat.name,
        ort: bereiche[kandidat.entity_id] || kandidat.name,
        art: kandidat.art === 'sonstige' ? 'bewegung' : kandidat.art,
        linie,
        modi: [],
        verzoegert: linie === 'einbruch',
        ausloesezustand: 'on',
        aktiv: true,
      });
      melderSpeichern(); melderZeichnen(); vorschlaegeZeichnen();
    };
    zeile.appendChild(knopf);
    kasten.appendChild(zeile);
  }
  if (!gezeigt) kasten.appendChild(el('div', 'leer', 'Nichts gefunden.'));
}

$('melder-suche').oninput = vorschlaegeZeichnen;
$('melder-filter').onchange = vorschlaegeZeichnen;

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
      `Bedienfeld-Zustand: ${modus.panel_zustand}`));
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

function linienZeichnen() {
  const liste = $('linien-liste');
  liste.textContent = '';
  for (const [schluessel, linie] of Object.entries(Z.konfig.linien)) {
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

const STUFENTEXT = {
  voralarm: ['Voralarm', 'Während der Eintrittsverzögerung, bevor der Alarm '
    + 'losgeht. Wer in dieser Zeit entschärft, soll nicht geweckt werden – '
    + 'deshalb ist die Stufe im Regelfall aus.'],
  alarm: ['Alarm', 'Der Ernstfall.'],
  entwarnung: ['Entwarnung', 'Nach dem Entschärfen. Ohne sie bleibt nach dem '
    + 'Push offen, ob jemand reagiert hat oder ob die Meldung ausgelaufen ist.'],
};

function meldewegeZeichnen() {
  const liste = $('meldewege-liste');
  liste.textContent = '';
  for (const [linieSchluessel, linie] of Object.entries(Z.konfig.linien)) {
    if (!linie.aktiv) continue;
    const karte = el('div', 'karte');
    karte.appendChild(el('h2', null, linie.name));
    const stufen = Z.konfig.eskalation[linieSchluessel] || {};
    for (const [stufeSchluessel, stufe] of Object.entries(stufen)) {
      karte.appendChild(stufeZeichnen(linieSchluessel, stufeSchluessel, stufe));
    }
    liste.appendChild(karte);
  }
}

function stufeZeichnen(linieSchluessel, stufeSchluessel, stufe) {
  const [titel, hilfe] = STUFENTEXT[stufeSchluessel] || [stufeSchluessel, ''];
  const kasten = el('div', 'stufe');

  const kopf = el('div', 'stufe-kopf');
  const links = el('div');
  links.appendChild(el('strong', null, titel));
  links.appendChild(el('div', 'hilfe', hilfe));
  kopf.appendChild(links);

  const rechts = el('div', 'zeile');
  rechts.style.margin = '0';
  const an = el('label');
  an.style.cssText = 'display:flex;gap:6px;color:var(--text)';
  const anKasten = el('input');
  anKasten.type = 'checkbox';
  anKasten.checked = stufe.aktiv !== false;
  anKasten.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { aktiv: anKasten.checked });
  an.appendChild(anKasten);
  an.appendChild(el('span', null, 'aktiv'));
  rechts.appendChild(an);

  const probe = el('button', 'knopf klein leise', 'Einmal auslösen');
  probe.title = 'Schickt diese Stufe jetzt ab – so lässt sich prüfen, ob der '
    + 'kritische Push wirklich durch den Fokusmodus kommt.';
  probe.onclick = async () => {
    const antwort = await schicke('api/probe',
      { linie: linieSchluessel, stufe: stufeSchluessel });
    tost(antwort.getan?.unterdrueckt
      ? 'Trockenlauf – es ging nichts hinaus.'
      : `Abgeschickt: ${antwort.getan.push.length} Push, `
        + `${antwort.getan.sprache.length} Ansagen.`);
  };
  rechts.appendChild(probe);
  kopf.appendChild(rechts);
  kasten.appendChild(kopf);

  const spalten = el('div', 'stufe-spalten');

  /* kaestchen() leert seinen Kasten, bevor es zeichnet. Jede Liste bekommt
     deshalb einen eigenen - sonst löscht sie die Überschrift darüber und,
     wo zwei Listen nebeneinander stehen, gleich die erste mit. */
  const gruppe = (ueberschrift, eltern) => {
    eltern.appendChild(el('h3', null, ueberschrift));
    const kasten = el('div');
    eltern.appendChild(kasten);
    return kasten;
  };

  const push = el('div');
  kaestchen(gruppe('Push aufs Telefon', push),
    (Z.auswahl?.meldewege?.push || []).map((d) =>
      ({ entity_id: d.dienst, name: d.name })), stufe.push || [], (auswahl) =>
    aendern(linieSchluessel, stufeSchluessel, { push: auswahl }));
  const kritisch = el('label', 'schalterzeile');
  const kritischKasten = el('input');
  kritischKasten.type = 'checkbox';
  kritischKasten.checked = !!stufe.kritisch;
  kritischKasten.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { kritisch: kritischKasten.checked });
  kritisch.appendChild(kritischKasten);
  const kritischText = el('span');
  kritischText.appendChild(el('strong', null, 'Kritischer Push'));
  kritischText.appendChild(el('small', null,
    'Durchbricht den Fokusmodus. Für den Ernstfall gedacht, nicht für '
    + 'Hinweise.'));
  kritisch.appendChild(kritischText);
  push.appendChild(kritisch);
  spalten.appendChild(push);

  const sprache = el('div');
  kaestchen(gruppe('Ansage über Lautsprecher', sprache),
    (Z.auswahl?.meldewege?.sprache || []).map((d) =>
      ({ entity_id: d.dienst, name: d.name })), stufe.alexa || [], (auswahl) =>
    aendern(linieSchluessel, stufeSchluessel, { alexa: auswahl }));
  spalten.appendChild(sprache);

  const licht = el('div');
  kaestchen(gruppe('Licht', licht), Z.auswahl?.lichter || [],
    stufe.licht || [], (auswahl) =>
    aendern(linieSchluessel, stufeSchluessel, { licht: auswahl }));
  const farbe = el('label');
  farbe.appendChild(document.createTextNode('Farbe'));
  const farbfeld = el('input');
  farbfeld.type = 'color';
  farbfeld.value = rgbZuHex(stufe.licht_farbe || [255, 0, 0]);
  farbfeld.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { licht_farbe: hexZuRgb(farbfeld.value) });
  farbe.appendChild(farbfeld);
  licht.appendChild(farbe);
  kaestchen(gruppe('Sirene oder Steckdose', licht), Z.auswahl?.schalter || [],
    stufe.schalter || [], (auswahl) =>
    aendern(linieSchluessel, stufeSchluessel, { schalter: auswahl }));
  spalten.appendChild(licht);

  kasten.appendChild(spalten);

  const text = el('label');
  text.style.marginTop = '12px';
  text.appendChild(document.createTextNode(
    'Eigener Text (leer = vorgegebener Satz). Platzhalter: {ausloeser} {ort} '
    + '{modus} {rest} {zeit}'));
  const textfeld = el('input');
  textfeld.type = 'text';
  textfeld.style.width = '100%';
  textfeld.value = stufe.text || '';
  textfeld.onchange = () => aendern(linieSchluessel, stufeSchluessel,
    { text: textfeld.value });
  text.appendChild(textfeld);
  kasten.appendChild(text);

  const persistent = el('label', 'schalterzeile');
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
  kasten.appendChild(persistent);

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
    const unter = [`Linie: ${automation.art}`,
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
      zeile.appendChild(el('div', 'p-art ' + eintrag.art, eintrag.art));
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
