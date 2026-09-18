/* Dashboard-Karte des Alarmanlagen-Managers.
 *
 * Sie kommt an den Ingress-Zugang des Add-ons nicht heran und braucht ihn
 * auch nicht: Am Bedienfeld hängt alles als Attribut. Eine Quelle, keine
 * zweite Wahrheit.
 *
 * Drei Fallen, die hier schon zugeschlagen haben und deshalb ausdrücklich
 * vermieden werden:
 *  - Kein Apostroph-Rückwärts in einem CSS-Kommentar. Das CSS lebt in einem
 *    Template-String; ein einziges Zeichen beendet ihn, und die Karte
 *    bleibt leer.
 *  - box-sizing wird selbst gesetzt. Ein Schattenbaum erbt keinen Reset von
 *    der Seite, und ohne ihn kommen Rand und Polster zur Spaltenbreite
 *    hinzu.
 *  - Auf keine Entität wird ohne Prüfung zugegriffen. Eine gelöschte
 *    Entität hat schon einmal die ganze Karte zum Absturz gebracht.
 */

const ZUSTAND = {
  disarmed: { text: 'Entschärft', symbol: 'mdi:shield-off-outline', farbe: 'gut' },
  arming: { text: 'Schaltet scharf', symbol: 'mdi:shield-sync-outline', farbe: 'warn' },
  armed_away: { text: 'Scharf', symbol: 'mdi:shield-lock', farbe: 'aktiv' },
  armed_vacation: { text: 'Scharf', symbol: 'mdi:shield-airplane', farbe: 'aktiv' },
  armed_night: { text: 'Scharf', symbol: 'mdi:shield-moon', farbe: 'aktiv' },
  armed_home: { text: 'Teilscharf', symbol: 'mdi:shield-home', farbe: 'aktiv' },
  pending: { text: 'Eintrittsverzögerung', symbol: 'mdi:shield-alert-outline', farbe: 'warn' },
  triggered: { text: 'Alarm', symbol: 'mdi:alarm-light', farbe: 'schlecht' },
  disarming: { text: 'Entschärft gerade', symbol: 'mdi:shield-off-outline', farbe: 'gut' },
  unavailable: { text: 'Nicht erreichbar', symbol: 'mdi:shield-off', farbe: 'aus' },
  unknown: { text: 'Unbekannt', symbol: 'mdi:shield-off', farbe: 'aus' },
};

const SKALEN = { klein: 1, normal: 1.1, gross: 1.2, riesig: 1.45 };

const VORGABE = {
  entity: 'alarm_control_panel.alarmanlage_bedienfeld',
  hausmodus_entity: 'select.alarmanlage_hausmodus',
  titel: 'Alarmanlage',
  textgroesse: 'gross',
  knoepfe: true,
  zeige_marken: true,
  zeige_fortschritt: true,
  zeige_kontakte: true,
  zeige_ausloeser: true,
};

/* ===================================================================
 * Die Karte
 * =================================================================== */

class AlarmanlageCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._gezeichnet = false;
    this._takt = null;
  }

  static getConfigElement() {
    return document.createElement('alarmanlage-card-editor');
  }

  static getStubConfig(hass) {
    /* Das Bedienfeld suchen, statt den Namen zu raten: Wer den
       Entitätspräfix geändert hat, bekommt sonst eine leere Karte. */
    const gefunden = Object.keys(hass?.states || {})
      .find((e) => e.startsWith('alarm_control_panel.')
        && hass.states[e].attributes.hausmodus !== undefined);
    return { ...VORGABE, entity: gefunden || VORGABE.entity };
  }

  setConfig(konfig) {
    this._konfig = { ...VORGABE, ...(konfig || {}) };
    this._gezeichnet = false;
    if (this.shadowRoot) this.shadowRoot.innerHTML = '';
  }

  set hass(hass) {
    this._hass = hass;
    this._zeichnen();
    /* Die Verzögerungen zählen sekundenweise herunter. Home Assistant
       schickt in dieser Zeit keine Zustandsänderung, also muss die Karte
       selbst ticken. */
    if (!this._takt) this._takt = setInterval(() => this._fristZeichnen(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._takt);
    this._takt = null;
  }

  getCardSize() {
    return this._konfig?.knoepfe === false ? 3 : 4;
  }

  _skala() {
    const wert = this._konfig.textgroesse;
    return typeof wert === 'number' ? wert : (SKALEN[wert] || 1.2);
  }

  _zeichnen() {
    if (!this._hass || !this._konfig) return;
    const panel = this._hass.states[this._konfig.entity];

    if (!this._gezeichnet) {
      this.shadowRoot.innerHTML = this._geruest();
      this._gezeichnet = true;
      this._verdrahten();
    }

    const wurzel = this.shadowRoot;
    if (!panel) {
      wurzel.querySelector('.inhalt').innerHTML =
        '<div class="leer">Die Entität <code>'
        + this._entschaerft(this._konfig.entity)
        + '</code> gibt es nicht. Läuft das Add-on?</div>';
      return;
    }

    const a = panel.attributes || {};
    const info = ZUSTAND[panel.state] || ZUSTAND.unknown;

    wurzel.querySelector('.kachel').className = 'kachel ' + info.farbe;
    wurzel.querySelector('.symbol').setAttribute('icon', info.symbol);
    wurzel.querySelector('.name').textContent =
      a.modus_name && panel.state.startsWith('armed')
        ? info.text + ' – ' + a.modus_name : info.text;

    const seit = a.zustand_seit ? new Date(a.zustand_seit) : null;
    wurzel.querySelector('.seit').textContent = seit
      ? 'seit ' + seit.toLocaleString('de-DE',
        { weekday: 'short', hour: '2-digit', minute: '2-digit' })
      : '';

    this._fristZeichnen();
    this._markenZeichnen(a);
    this._zeilenZeichnen(a);
    this._knoepfeZeichnen(panel);
  }

  /* Alles, was man wissen muss, bevor man sich auf die Anlage verlässt.
     Der Trockenlauf steht ganz oben: Eine Karte, die "scharf" zeigt,
     während das Add-on nichts hinausschickt, wäre die gefährlichste
     Anzeige im ganzen Haus. */
  _markenZeichnen(a) {
    const hinweise = this.shadowRoot.querySelector('.marken');
    hinweise.innerHTML = '';
    hinweise.style.display = this._konfig.zeige_marken === false ? 'none' : '';
    if (this._konfig.zeige_marken === false) return;
    const marke = (text, art) => {
      const k = document.createElement('span');
      k.className = 'marke ' + (art || '');
      k.textContent = text;
      hinweise.appendChild(k);
    };
    if (a.trockenlauf) marke('Trockenlauf – es geht nichts hinaus', 'warn');
    if (a.automatik === false) marke('Automatik aus', 'warn');
    if (a.nachlaufsperre) marke('Nachlaufsperre');
    if (a.verbunden === false) marke('Keine Verbindung', 'schlecht');
    for (const ort of a.offene_alarme || []) marke('Alarm: ' + ort, 'schlecht');
    if ((a.ueberbrueckt || []).length) {
      marke((a.ueberbrueckt || []).length + ' überbrückt');
    }
  }

  _zeilenZeichnen(a) {
    const zeigen = (wahl, klasse, symbol, text) => {
      const kasten = this.shadowRoot.querySelector('.' + klasse);
      const an = wahl !== false && !!text;
      kasten.style.display = an ? '' : 'none';
      if (!an) return;
      kasten.innerHTML = '';
      const icon = document.createElement('ha-icon');
      icon.setAttribute('icon', symbol);
      kasten.appendChild(icon);
      const span = document.createElement('span');
      span.textContent = text;
      kasten.appendChild(span);
    };

    const offen = a.offene_kontakte || [];
    zeigen(this._konfig.zeige_kontakte, 'offen', 'mdi:door-open',
      offen.length ? 'Offen: ' + offen.join(', ') : '');
    zeigen(this._konfig.zeige_ausloeser, 'ausloeser', 'mdi:motion-sensor',
      a.letzter_ausloeser ? 'Zuletzt: ' + a.letzter_ausloeser : '');

    /* Eine Trennlinie ohne etwas darunter trennt nichts. */
    const wurzel = this.shadowRoot;
    const etwasDa = ['offen', 'ausloeser'].some((k) =>
      wurzel.querySelector('.' + k).style.display !== 'none');
    wurzel.querySelector('.trenner').style.display = etwasDa ? '' : 'none';
  }

  _fristZeichnen() {
    if (!this._gezeichnet || !this._hass) return;
    const panel = this._hass.states[this._konfig.entity];
    const feld = this.shadowRoot.querySelector('.frist');
    const balken = this.shadowRoot.querySelector('.balken');
    if (!feld || !panel) return;
    const a = panel.attributes || {};

    if (a.rest_sekunden === null || a.rest_sekunden === undefined) {
      feld.textContent = '';
      balken.style.display = 'none';
      return;
    }

    /* Der Wert stammt aus der letzten Meldung. Wie viel davon inzwischen
       vergangen ist, rechnet die Karte selbst mit – sonst stünde dreißig
       Sekunden lang dieselbe Zahl da. */
    const gemeldet = new Date(panel.last_updated).getTime();
    const rest = Math.max(0,
      Math.round(a.rest_sekunden - (Date.now() - gemeldet) / 1000));
    const minuten = Math.floor(rest / 60);
    const zeit = minuten + ':' + String(rest % 60).padStart(2, '0');

    feld.textContent = panel.state === 'arming'
      ? 'noch ' + zeit + ' zum Verlassen'
      : panel.state === 'pending'
        ? 'noch ' + zeit + ' bis zum Alarm'
        : panel.state === 'triggered'
          ? 'Alarm läuft noch ' + zeit
          : 'noch ' + zeit;

    const gesamt = a.frist_gesamt;
    if (this._konfig.zeige_fortschritt === false || !gesamt) {
      balken.style.display = 'none';
      return;
    }
    balken.style.display = '';
    const anteil = Math.max(0, Math.min(1, rest / gesamt));
    balken.firstElementChild.style.width = (anteil * 100) + '%';
    balken.className = 'balken ' + (ZUSTAND[panel.state] || {}).farbe;
  }

  _knoepfeZeichnen(panel) {
    const kasten = this.shadowRoot.querySelector('.knoepfe');
    if (this._konfig.knoepfe === false) { kasten.style.display = 'none'; return; }
    kasten.style.display = '';

    const wahl = this._hass.states[this._konfig.hausmodus_entity];
    const optionen = wahl?.attributes?.options || [];
    const jetzt = wahl?.state;
    const stand = optionen.join('|') + '||' + jetzt + '||' + panel.state;
    if (kasten.dataset.stand === stand) return;
    kasten.dataset.stand = stand;
    kasten.innerHTML = '';

    if (!optionen.length) {
      const hinweis = document.createElement('div');
      hinweis.className = 'leer';
      hinweis.textContent = 'Kein Hausmodus gefunden ('
        + this._konfig.hausmodus_entity + ').';
      kasten.appendChild(hinweis);
      return;
    }

    for (const option of optionen) {
      const knopf = document.createElement('button');
      knopf.className = 'knopf' + (option === jetzt ? ' an' : '');
      knopf.textContent = option;
      knopf.addEventListener('click', () => {
        this._hass.callService('select', 'select_option', {
          entity_id: this._konfig.hausmodus_entity,
          option,
        });
      });
      kasten.appendChild(knopf);
    }

    if (panel.state === 'triggered' || panel.state === 'pending') {
      const stopp = document.createElement('button');
      stopp.className = 'knopf gefahr';
      stopp.textContent = 'Alarm aus';
      stopp.addEventListener('click', () => {
        this._hass.callService('alarm_control_panel', 'alarm_disarm', {
          entity_id: this._konfig.entity,
        });
      });
      kasten.appendChild(stopp);
    }
  }

  _verdrahten() {
    this.shadowRoot.querySelector('.kachel').addEventListener('click', () => {
      /* Der übliche Griff in Home Assistant: Tippen öffnet die Entität. */
      const ereignis = new Event('hass-more-info', {
        bubbles: true, composed: true,
      });
      ereignis.detail = { entityId: this._konfig.entity };
      this.dispatchEvent(ereignis);
    });
  }

  _geruest() {
    const titel = this._konfig.titel
      ? ' header="' + this._entschaerft(this._konfig.titel) + '"' : '';
    return '<style>' + this._css() + '</style>'
      + '<ha-card' + titel + '>'
      + '<div class="inhalt">'
      + '  <div class="marken"></div>'
      + '  <div class="kachel">'
      + '    <div class="ring"><ha-icon class="symbol"></ha-icon></div>'
      + '    <div class="texte">'
      + '      <div class="name"></div>'
      + '      <div class="seit"></div>'
      + '      <div class="frist"></div>'
      + '      <div class="balken"><div></div></div>'
      + '    </div>'
      + '  </div>'
      + '  <div class="trenner"></div>'
      + '  <div class="zeile offen"></div>'
      + '  <div class="zeile ausloeser"></div>'
      + '  <div class="knoepfe"></div>'
      + '</div>'
      + '</ha-card>';
  }

  _entschaerft(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  _css() {
    return `
      :host { --skala: ${this._skala()}; }
      * { box-sizing: border-box; }
      .inhalt {
        padding: 0 16px 16px; display: flex; flex-direction: column;
        gap: calc(10px * var(--skala));
      }
      .marken { display: flex; gap: 6px; flex-wrap: wrap; }
      .marken:empty { display: none; }
      .marke {
        font-size: calc(11px * var(--skala));
        padding: calc(3px * var(--skala)) calc(9px * var(--skala));
        border-radius: 999px;
        border: 1px solid var(--divider-color);
        color: var(--secondary-text-color);
      }
      .marke.warn { border-color: var(--warning-color); color: var(--warning-color); }
      .marke.schlecht { border-color: var(--error-color); color: var(--error-color); }

      /* Kein eigener Kasten im Kasten. Eine Karte sitzt im Theme des
         Benutzers, und ein Rahmen mit eigenem Hintergrund faellt dort als
         Fremdkoerper auf - besonders bei halbtransparenten Karten. Die
         Farbe traegt deshalb das Symbol, so wie es die uebrigen Karten in
         Home Assistant halten. */
      .kachel {
        display: flex; align-items: center; gap: calc(14px * var(--skala));
        cursor: pointer;
      }
      .kachel.aus { opacity: .6; }
      .ring {
        width: calc(46px * var(--skala)); height: calc(46px * var(--skala));
        border-radius: 50%; display: grid; place-items: center;
        background: var(--secondary-background-color); flex: 0 0 auto;
      }
      .symbol {
        --mdc-icon-size: calc(26px * var(--skala));
        color: var(--secondary-text-color);
      }
      /* color-mix statt fester Farbwerte: Der getoente Kreis folgt damit
         jedem Theme, auch einem selbstgebauten. */
      .kachel.gut .ring {
        background: color-mix(in srgb, var(--success-color, #2e9e5b) 20%, transparent);
      }
      .kachel.gut .symbol { color: var(--success-color, #2e9e5b); }
      .kachel.aktiv .ring {
        background: color-mix(in srgb, var(--primary-color) 20%, transparent);
      }
      .kachel.aktiv .symbol { color: var(--primary-color); }
      .kachel.warn .ring {
        background: color-mix(in srgb, var(--warning-color) 22%, transparent);
      }
      .kachel.warn .symbol { color: var(--warning-color); }
      .kachel.schlecht .ring {
        background: color-mix(in srgb, var(--error-color) 22%, transparent);
      }
      .kachel.schlecht .symbol { color: var(--error-color); }
      .kachel.schlecht .ring { animation: pochen 1s infinite; }
      @keyframes pochen {
        0%, 100% { box-shadow: 0 0 0 0 rgba(200, 50, 50, .45); }
        50% { box-shadow: 0 0 0 10px rgba(200, 50, 50, 0); }
      }
      @media (prefers-reduced-motion: reduce) {
        .kachel.schlecht .ring { animation: none; }
      }

      .texte { min-width: 0; flex: 1 1 auto; }
      .name { font-size: calc(17px * var(--skala)); font-weight: 600; }
      .seit { font-size: calc(12px * var(--skala)); color: var(--secondary-text-color); }
      .frist {
        font-size: calc(13px * var(--skala)); font-weight: 600;
        color: var(--warning-color); font-variant-numeric: tabular-nums;
      }
      .frist:empty { display: none; }

      /* Der Balken zeigt, wie viel von der Frist noch übrig ist. Eine Zahl
         allein sagt nicht, ob es knapp wird. */
      .balken {
        height: 4px; border-radius: 999px; margin-top: 6px;
        background: var(--divider-color); overflow: hidden;
      }
      .balken > div {
        height: 100%; width: 0; border-radius: 999px;
        background: var(--warning-color); transition: width 1s linear;
      }
      .balken.schlecht > div { background: var(--error-color); }

      .trenner {
        height: 1px; background: var(--divider-color); opacity: .5;
        margin: calc(2px * var(--skala)) 0;
      }
      .zeile {
        display: flex; align-items: center; gap: 8px;
        font-size: calc(13px * var(--skala)); color: var(--secondary-text-color);
        min-width: 0;
      }
      .zeile ha-icon {
        --mdc-icon-size: calc(16px * var(--skala)); flex: 0 0 auto;
      }
      .zeile span {
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }

      .knoepfe { display: flex; gap: 6px; flex-wrap: wrap; }
      .knopf {
        flex: 1 1 calc(90px * var(--skala));
        min-width: 0;
        padding: calc(9px * var(--skala)) calc(8px * var(--skala));
        border-radius: 12px;
        border: 0;
        /* Aus der Textfarbe gemischt, nicht aus dem Kartenhintergrund:
           Auf halbtransparenten Karten ist der naemlich fast unsichtbar. */
        background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
        color: var(--primary-text-color);
        font: inherit; font-size: calc(13px * var(--skala));
        cursor: pointer;
      }
      .knopf:hover {
        background: color-mix(in srgb, var(--primary-text-color) 14%, transparent);
      }
      .knopf.an {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .knopf.gefahr {
        background: var(--error-color); border-color: var(--error-color);
        color: #fff; flex-basis: 100%;
      }
      .leer {
        font-size: calc(13px * var(--skala)); color: var(--secondary-text-color);
      }
      code { font-size: .9em; }
    `;
  }
}

customElements.define('alarmanlage-card', AlarmanlageCard);

/* ===================================================================
 * Der Editor
 *
 * Über ha-form, nicht über eigene Eingabefelder: Das bringt
 * Entitätsauswahl, Schalter und Auswahllisten im Aussehen von Home
 * Assistant mit, und es folgt dem Thema des Benutzers von selbst.
 * =================================================================== */

const FELDER = [
  { name: 'titel', selector: { text: {} } },
  {
    name: 'entity',
    required: true,
    selector: { entity: { domain: 'alarm_control_panel' } },
  },
  {
    name: 'hausmodus_entity',
    selector: { entity: { domain: 'select' } },
  },
  {
    name: 'textgroesse',
    selector: {
      select: {
        mode: 'dropdown',
        options: [
          { value: 'klein', label: 'klein' },
          { value: 'normal', label: 'normal' },
          { value: 'gross', label: 'groß (Vorgabe)' },
          { value: 'riesig', label: 'riesig – für Wandtablets' },
        ],
      },
    },
  },
  {
    name: 'anzeige',
    type: 'expandable',
    schema: [
      { name: 'knoepfe', selector: { boolean: {} } },
      { name: 'zeige_marken', selector: { boolean: {} } },
      { name: 'zeige_fortschritt', selector: { boolean: {} } },
      { name: 'zeige_kontakte', selector: { boolean: {} } },
      { name: 'zeige_ausloeser', selector: { boolean: {} } },
    ],
  },
];

const BESCHRIFTUNG = {
  titel: 'Überschrift',
  entity: 'Bedienfeld',
  hausmodus_entity: 'Hausmodus (für die Knöpfe)',
  textgroesse: 'Textgröße',
  anzeige: 'Was die Karte zeigt',
  knoepfe: 'Knöpfe für den Hausmodus',
  zeige_marken: 'Hinweise (Trockenlauf, Nachlaufsperre …)',
  zeige_fortschritt: 'Balken während der Verzögerung',
  zeige_kontakte: 'Offene Kontakte',
  zeige_ausloeser: 'Letzter Auslöser',
};

const ERKLAERUNG = {
  entity: 'Das Bedienfeld des Alarmanlagen-Managers. Es trägt alle Angaben '
    + 'als Attribute – die Karte braucht sonst nichts.',
  textgroesse: 'Alles skaliert mit: Schrift, Symbole, Knöpfe. „Riesig“ ist '
    + 'für Tablets gedacht, die man aus anderthalb Metern abliest.',
};

class AlarmanlageCardEditor extends HTMLElement {
  setConfig(konfig) {
    this._konfig = { ...VORGABE, ...(konfig || {}) };
    this._zeichnen();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  _zeichnen() {
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.addEventListener('value-changed', (ereignis) => {
        ereignis.stopPropagation();
        this.dispatchEvent(new CustomEvent('config-changed', {
          detail: { config: ereignis.detail.value },
          bubbles: true, composed: true,
        }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = FELDER;
    this._form.data = this._konfig;
    this._form.computeLabel = (feld) => BESCHRIFTUNG[feld.name] || feld.name;
    this._form.computeHelper = (feld) => ERKLAERUNG[feld.name] || '';
  }
}

customElements.define('alarmanlage-card-editor', AlarmanlageCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'alarmanlage-card',
  name: 'Alarmanlage',
  description: 'Zustand, Hausmodus und offene Kontakte des '
    + 'Alarmanlagen-Managers',
  preview: true,
  documentationURL: 'https://github.com/Melle79/HA-alarmanlage',
});

console.info('%c ALARMANLAGE-CARD %c geladen ',
  'color:#fff;background:#cf3a3a;font-weight:700',
  'color:#cf3a3a;background:#fff');
