/* Dashboard-Karte des Alarmanlagen-Managers.
 *
 * Sie kommt an den Ingress-Zugang des Add-ons nicht heran und braucht ihn
 * auch nicht: Am Bedienfeld hängt alles als Attribut. Eine Quelle, keine
 * zweite Wahrheit.
 *
 * Zwei Fallen, die hier schon zugeschlagen haben und deshalb ausdrücklich
 * vermieden werden:
 *  - Kein Apostroph-Rückwärts in einem CSS-Kommentar. Das CSS lebt in einem
 *    Template-String; ein einziges Zeichen beendet ihn, und die Karte
 *    bleibt leer.
 *  - box-sizing wird selbst gesetzt. Ein Schattenbaum erbt keinen Reset von
 *    der Seite, und ohne ihn kommen Rand und Polster zur Spaltenbreite
 *    hinzu.
 */

const ZUSTAND = {
  disarmed: { text: 'Entschärft', symbol: 'mdi:shield-off-outline', farbe: 'gut' },
  arming: { text: 'Schaltet scharf', symbol: 'mdi:shield-sync-outline', farbe: 'warn' },
  /* Der Text nennt nur die Art der Schärfung. Welcher Modus gilt, sagt
     der Name des Modus daneben - sonst stünde "Scharf - Urlaub - Urlaub"
     da, sobald jemand seinen Modus wie den Zustand benennt. */
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

class AlarmanlageCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._gezeichnet = false;
    this._takt = null;
  }

  setConfig(konfig) {
    this._konfig = {
      entity: konfig.entity || 'alarm_control_panel.alarmanlage',
      hausmodus_entity: konfig.hausmodus_entity || 'select.alarmanlage_hausmodus',
      titel: konfig.titel ?? konfig.title ?? 'Alarmanlage',
      /* Vorgabe gross, weil die Karte auch am Wandtablett im Flur hängt und
         11-px-Text dort aus anderthalb Metern unlesbar ist. */
      textgroesse: konfig.textgroesse || 'gross',
      knoepfe: konfig.knoepfe !== false,
      protokollzeilen: konfig.protokollzeilen ?? 0,
    };
    this._gezeichnet = false;
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

  getCardSize() { return 4; }

  static getStubConfig() {
    return { entity: 'alarm_control_panel.alarmanlage' };
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
        '<div class="leer">Die Entität ' + this._konfig.entity
        + ' gibt es nicht. Läuft das Add-on?</div>';
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

    /* Hinweise. Der Trockenlauf steht ganz oben: Eine Karte, die "scharf"
       zeigt, während das Add-on nichts hinausschickt, wäre die
       gefährlichste Anzeige im ganzen Haus. */
    const hinweise = wurzel.querySelector('.hinweise');
    hinweise.innerHTML = '';
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
    if ((a.offene_alarme || []).length) {
      marke('Alarm: ' + a.offene_alarme.join(', '), 'schlecht');
    }

    const offen = a.offene_kontakte || [];
    const offenKasten = wurzel.querySelector('.offen');
    offenKasten.innerHTML = offen.length
      ? '<span class="klein">Offen: </span>' + offen.join(', ')
      : '';
    offenKasten.style.display = offen.length ? '' : 'none';

    const ausloeser = wurzel.querySelector('.ausloeser');
    ausloeser.textContent = a.letzter_ausloeser
      ? 'Zuletzt: ' + a.letzter_ausloeser : '';
    ausloeser.style.display = a.letzter_ausloeser ? '' : 'none';

    this._knoepfeZeichnen(panel);
  }

  _fristZeichnen() {
    if (!this._gezeichnet || !this._hass) return;
    const panel = this._hass.states[this._konfig.entity];
    const feld = this.shadowRoot.querySelector('.frist');
    if (!feld || !panel) return;
    const a = panel.attributes || {};
    if (a.rest_sekunden === null || a.rest_sekunden === undefined) {
      feld.textContent = '';
      return;
    }
    /* Der Wert stammt aus der letzten Meldung. Wie viel davon inzwischen
       vergangen ist, rechnet die Karte selbst mit – sonst stünde dreißig
       Sekunden lang dieselbe Zahl da. */
    const gemeldet = new Date(panel.last_updated).getTime();
    const rest = Math.max(0,
      Math.round(a.rest_sekunden - (Date.now() - gemeldet) / 1000));
    const minuten = Math.floor(rest / 60);
    const sekunden = String(rest % 60).padStart(2, '0');
    const zeit = minuten + ':' + sekunden;
    feld.textContent = panel.state === 'arming'
      ? 'noch ' + zeit + ' zum Verlassen'
      : panel.state === 'pending'
        ? 'noch ' + zeit + ' bis zum Alarm'
        : panel.state === 'triggered'
          ? 'Alarm läuft noch ' + zeit
          : 'noch ' + zeit;
  }

  _knoepfeZeichnen(panel) {
    const kasten = this.shadowRoot.querySelector('.knoepfe');
    if (!this._konfig.knoepfe) { kasten.style.display = 'none'; return; }

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
    return '<style>' + this._css() + '</style>'
      + '<ha-card header="' + this._entschaerft(this._konfig.titel) + '">'
      + '<div class="inhalt">'
      + '  <div class="hinweise"></div>'
      + '  <div class="kachel">'
      + '    <div class="ring"><ha-icon class="symbol"></ha-icon></div>'
      + '    <div class="texte">'
      + '      <div class="name"></div>'
      + '      <div class="seit"></div>'
      + '      <div class="frist"></div>'
      + '    </div>'
      + '  </div>'
      + '  <div class="offen"></div>'
      + '  <div class="ausloeser"></div>'
      + '  <div class="knoepfe"></div>'
      + '</div>'
      + '</ha-card>';
  }

  _entschaerft(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  _css() {
    const skala = this._skala();
    return `
      :host { --skala: ${skala}; }
      * { box-sizing: border-box; }
      .inhalt { padding: 0 16px 16px; display: flex; flex-direction: column; gap: calc(10px * var(--skala)); }
      .hinweise { display: flex; gap: 6px; flex-wrap: wrap; }
      .hinweise:empty { display: none; }
      .marke {
        font-size: calc(11px * var(--skala));
        padding: calc(3px * var(--skala)) calc(9px * var(--skala));
        border-radius: 999px;
        border: 1px solid var(--divider-color);
        color: var(--secondary-text-color);
      }
      .marke.warn { border-color: var(--warning-color); color: var(--warning-color); }
      .marke.schlecht { border-color: var(--error-color); color: var(--error-color); }
      .kachel {
        display: flex; align-items: center; gap: calc(14px * var(--skala));
        padding: calc(12px * var(--skala));
        border-radius: 12px;
        border: 1px solid var(--divider-color);
        border-left: 5px solid var(--secondary-text-color);
        cursor: pointer;
      }
      .kachel.gut { border-left-color: var(--success-color, #2e9e5b); }
      .kachel.aktiv { border-left-color: var(--primary-color); }
      .kachel.warn { border-left-color: var(--warning-color); }
      .kachel.schlecht { border-left-color: var(--error-color); }
      .kachel.aus { opacity: .6; }
      .ring {
        width: calc(46px * var(--skala)); height: calc(46px * var(--skala));
        border-radius: 50%; display: grid; place-items: center;
        background: var(--secondary-background-color); flex: 0 0 auto;
      }
      .symbol { --mdc-icon-size: calc(26px * var(--skala)); color: var(--primary-text-color); }
      .kachel.schlecht .symbol { color: var(--error-color); }
      .kachel.schlecht .ring { animation: pochen 1s infinite; }
      @keyframes pochen {
        0%, 100% { box-shadow: 0 0 0 0 rgba(200, 50, 50, .45); }
        50% { box-shadow: 0 0 0 10px rgba(200, 50, 50, 0); }
      }
      @media (prefers-reduced-motion: reduce) {
        .kachel.schlecht .ring { animation: none; }
      }
      .texte { min-width: 0; }
      .name { font-size: calc(17px * var(--skala)); font-weight: 600; }
      .seit { font-size: calc(12px * var(--skala)); color: var(--secondary-text-color); }
      .frist {
        font-size: calc(13px * var(--skala)); font-weight: 600;
        color: var(--warning-color); font-variant-numeric: tabular-nums;
      }
      .frist:empty { display: none; }
      .offen, .ausloeser {
        font-size: calc(13px * var(--skala)); color: var(--secondary-text-color);
      }
      .klein { opacity: .75; }
      .knoepfe { display: flex; gap: 6px; flex-wrap: wrap; }
      .knopf {
        flex: 1 1 calc(90px * var(--skala));
        min-width: 0;
        padding: calc(9px * var(--skala)) calc(8px * var(--skala));
        border-radius: 10px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font: inherit; font-size: calc(13px * var(--skala));
        cursor: pointer;
      }
      .knopf:hover { border-color: var(--primary-color); }
      .knopf.an {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .knopf.gefahr {
        background: var(--error-color); border-color: var(--error-color);
        color: #fff; flex-basis: 100%;
      }
      .leer { font-size: calc(13px * var(--skala)); color: var(--secondary-text-color); }
    `;
  }
}

customElements.define('alarmanlage-card', AlarmanlageCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'alarmanlage-card',
  name: 'Alarmanlage',
  description: 'Zustand, Hausmodus und offene Kontakte des '
    + 'Alarmanlagen-Managers',
  preview: true,
});

console.info('%c ALARMANLAGE-CARD %c geladen ',
  'color:#fff;background:#cf3a3a;font-weight:700',
  'color:#cf3a3a;background:#fff');
