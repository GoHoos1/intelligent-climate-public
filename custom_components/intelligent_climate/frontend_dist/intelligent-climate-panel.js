const J = globalThis, fe = J.ShadowRoot && (J.ShadyCSS === void 0 || J.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, _e = /* @__PURE__ */ Symbol(), xe = /* @__PURE__ */ new WeakMap();
let Le = class {
  constructor(e, t, i) {
    if (this._$cssResult$ = !0, i !== _e) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = e, this.t = t;
  }
  get styleSheet() {
    let e = this.o;
    const t = this.t;
    if (fe && e === void 0) {
      const i = t !== void 0 && t.length === 1;
      i && (e = xe.get(t)), e === void 0 && ((this.o = e = new CSSStyleSheet()).replaceSync(this.cssText), i && xe.set(t, e));
    }
    return e;
  }
  toString() {
    return this.cssText;
  }
};
const Je = (r) => new Le(typeof r == "string" ? r : r + "", void 0, _e), se = (r, ...e) => {
  const t = r.length === 1 ? r[0] : e.reduce((i, a, n) => i + ((s) => {
    if (s._$cssResult$ === !0) return s.cssText;
    if (typeof s == "number") return s;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + s + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(a) + r[n + 1], r[0]);
  return new Le(t, r, _e);
}, Xe = (r, e) => {
  if (fe) r.adoptedStyleSheets = e.map((t) => t instanceof CSSStyleSheet ? t : t.styleSheet);
  else for (const t of e) {
    const i = document.createElement("style"), a = J.litNonce;
    a !== void 0 && i.setAttribute("nonce", a), i.textContent = t.cssText, r.appendChild(i);
  }
}, we = fe ? (r) => r : (r) => r instanceof CSSStyleSheet ? ((e) => {
  let t = "";
  for (const i of e.cssRules) t += i.cssText;
  return Je(t);
})(r) : r;
const { is: et, defineProperty: tt, getOwnPropertyDescriptor: it, getOwnPropertyNames: at, getOwnPropertySymbols: rt, getPrototypeOf: nt } = Object, oe = globalThis, ke = oe.trustedTypes, st = ke ? ke.emptyScript : "", ot = oe.reactiveElementPolyfillSupport, B = (r, e) => r, ue = { toAttribute(r, e) {
  switch (e) {
    case Boolean:
      r = r ? st : null;
      break;
    case Object:
    case Array:
      r = r == null ? r : JSON.stringify(r);
  }
  return r;
}, fromAttribute(r, e) {
  let t = r;
  switch (e) {
    case Boolean:
      t = r !== null;
      break;
    case Number:
      t = r === null ? null : Number(r);
      break;
    case Object:
    case Array:
      try {
        t = JSON.parse(r);
      } catch {
        t = null;
      }
  }
  return t;
} }, Ne = (r, e) => !et(r, e), Se = { attribute: !0, type: String, converter: ue, reflect: !1, useDefault: !1, hasChanged: Ne };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), oe.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let N = class extends HTMLElement {
  static addInitializer(e) {
    this._$Ei(), (this.l ??= []).push(e);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(e, t = Se) {
    if (t.state && (t.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(e) && ((t = Object.create(t)).wrapped = !0), this.elementProperties.set(e, t), !t.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), a = this.getPropertyDescriptor(e, i, t);
      a !== void 0 && tt(this.prototype, e, a);
    }
  }
  static getPropertyDescriptor(e, t, i) {
    const { get: a, set: n } = it(this.prototype, e) ?? { get() {
      return this[t];
    }, set(s) {
      this[t] = s;
    } };
    return { get: a, set(s) {
      const l = a?.call(this);
      n?.call(this, s), this.requestUpdate(e, l, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(e) {
    return this.elementProperties.get(e) ?? Se;
  }
  static _$Ei() {
    if (this.hasOwnProperty(B("elementProperties"))) return;
    const e = nt(this);
    e.finalize(), e.l !== void 0 && (this.l = [...e.l]), this.elementProperties = new Map(e.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(B("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(B("properties"))) {
      const t = this.properties, i = [...at(t), ...rt(t)];
      for (const a of i) this.createProperty(a, t[a]);
    }
    const e = this[Symbol.metadata];
    if (e !== null) {
      const t = litPropertyMetadata.get(e);
      if (t !== void 0) for (const [i, a] of t) this.elementProperties.set(i, a);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [t, i] of this.elementProperties) {
      const a = this._$Eu(t, i);
      a !== void 0 && this._$Eh.set(a, t);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(e) {
    const t = [];
    if (Array.isArray(e)) {
      const i = new Set(e.flat(1 / 0).reverse());
      for (const a of i) t.unshift(we(a));
    } else e !== void 0 && t.push(we(e));
    return t;
  }
  static _$Eu(e, t) {
    const i = t.attribute;
    return i === !1 ? void 0 : typeof i == "string" ? i : typeof e == "string" ? e.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((e) => this.enableUpdating = e), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((e) => e(this));
  }
  addController(e) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(e), this.renderRoot !== void 0 && this.isConnected && e.hostConnected?.();
  }
  removeController(e) {
    this._$EO?.delete(e);
  }
  _$E_() {
    const e = /* @__PURE__ */ new Map(), t = this.constructor.elementProperties;
    for (const i of t.keys()) this.hasOwnProperty(i) && (e.set(i, this[i]), delete this[i]);
    e.size > 0 && (this._$Ep = e);
  }
  createRenderRoot() {
    const e = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return Xe(e, this.constructor.elementStyles), e;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(!0), this._$EO?.forEach((e) => e.hostConnected?.());
  }
  enableUpdating(e) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((e) => e.hostDisconnected?.());
  }
  attributeChangedCallback(e, t, i) {
    this._$AK(e, i);
  }
  _$ET(e, t) {
    const i = this.constructor.elementProperties.get(e), a = this.constructor._$Eu(e, i);
    if (a !== void 0 && i.reflect === !0) {
      const n = (i.converter?.toAttribute !== void 0 ? i.converter : ue).toAttribute(t, i.type);
      this._$Em = e, n == null ? this.removeAttribute(a) : this.setAttribute(a, n), this._$Em = null;
    }
  }
  _$AK(e, t) {
    const i = this.constructor, a = i._$Eh.get(e);
    if (a !== void 0 && this._$Em !== a) {
      const n = i.getPropertyOptions(a), s = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : ue;
      this._$Em = a;
      const l = s.fromAttribute(t, n.type);
      this[a] = l ?? this._$Ej?.get(a) ?? l, this._$Em = null;
    }
  }
  requestUpdate(e, t, i, a = !1, n) {
    if (e !== void 0) {
      const s = this.constructor;
      if (a === !1 && (n = this[e]), i ??= s.getPropertyOptions(e), !((i.hasChanged ?? Ne)(n, t) || i.useDefault && i.reflect && n === this._$Ej?.get(e) && !this.hasAttribute(s._$Eu(e, i)))) return;
      this.C(e, t, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(e, t, { useDefault: i, reflect: a, wrapped: n }, s) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(e) && (this._$Ej.set(e, s ?? t ?? this[e]), n !== !0 || s !== void 0) || (this._$AL.has(e) || (this.hasUpdated || i || (t = void 0), this._$AL.set(e, t)), a === !0 && this._$Em !== e && (this._$Eq ??= /* @__PURE__ */ new Set()).add(e));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (t) {
      Promise.reject(t);
    }
    const e = this.scheduleUpdate();
    return e != null && await e, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
        for (const [a, n] of this._$Ep) this[a] = n;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [a, n] of i) {
        const { wrapped: s } = n, l = this[a];
        s !== !0 || this._$AL.has(a) || l === void 0 || this.C(a, void 0, n, l);
      }
    }
    let e = !1;
    const t = this._$AL;
    try {
      e = this.shouldUpdate(t), e ? (this.willUpdate(t), this._$EO?.forEach((i) => i.hostUpdate?.()), this.update(t)) : this._$EM();
    } catch (i) {
      throw e = !1, this._$EM(), i;
    }
    e && this._$AE(t);
  }
  willUpdate(e) {
  }
  _$AE(e) {
    this._$EO?.forEach((t) => t.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(e)), this.updated(e);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(e) {
    return !0;
  }
  update(e) {
    this._$Eq &&= this._$Eq.forEach((t) => this._$ET(t, this[t])), this._$EM();
  }
  updated(e) {
  }
  firstUpdated(e) {
  }
};
N.elementStyles = [], N.shadowRootOptions = { mode: "open" }, N[B("elementProperties")] = /* @__PURE__ */ new Map(), N[B("finalized")] = /* @__PURE__ */ new Map(), ot?.({ ReactiveElement: N }), (oe.reactiveElementVersions ??= []).push("2.1.2");
const be = globalThis, ze = (r) => r, te = be.trustedTypes, Ce = te ? te.createPolicy("lit-html", { createHTML: (r) => r }) : void 0, He = "$lit$", T = `lit$${Math.random().toFixed(9).slice(2)}$`, Re = "?" + T, lt = `<${Re}>`, M = document, V = () => M.createComment(""), Y = (r) => r === null || typeof r != "object" && typeof r != "function", ye = Array.isArray, ct = (r) => ye(r) || typeof r?.[Symbol.iterator] == "function", de = `[ 	
\f\r]`, j = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, Ae = /-->/g, Te = />/g, D = RegExp(`>|${de}(?:([^\\s"'>=/]+)(${de}*=${de}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), Ee = /'/g, De = /"/g, qe = /^(?:script|style|textarea|title)$/i, Fe = (r) => (e, ...t) => ({ _$litType$: r, strings: e, values: t }), c = Fe(1), A = Fe(2), R = /* @__PURE__ */ Symbol.for("lit-noChange"), g = /* @__PURE__ */ Symbol.for("lit-nothing"), Pe = /* @__PURE__ */ new WeakMap(), P = M.createTreeWalker(M, 129);
function Ze(r, e) {
  if (!ye(r) || !r.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return Ce !== void 0 ? Ce.createHTML(e) : e;
}
const dt = (r, e) => {
  const t = r.length - 1, i = [];
  let a, n = e === 2 ? "<svg>" : e === 3 ? "<math>" : "", s = j;
  for (let l = 0; l < t; l++) {
    const o = r[l];
    let p, m, d = -1, h = 0;
    for (; h < o.length && (s.lastIndex = h, m = s.exec(o), m !== null); ) h = s.lastIndex, s === j ? m[1] === "!--" ? s = Ae : m[1] !== void 0 ? s = Te : m[2] !== void 0 ? (qe.test(m[2]) && (a = RegExp("</" + m[2], "g")), s = D) : m[3] !== void 0 && (s = D) : s === D ? m[0] === ">" ? (s = a ?? j, d = -1) : m[1] === void 0 ? d = -2 : (d = s.lastIndex - m[2].length, p = m[1], s = m[3] === void 0 ? D : m[3] === '"' ? De : Ee) : s === De || s === Ee ? s = D : s === Ae || s === Te ? s = j : (s = D, a = void 0);
    const f = s === D && r[l + 1].startsWith("/>") ? " " : "";
    n += s === j ? o + lt : d >= 0 ? (i.push(p), o.slice(0, d) + He + o.slice(d) + T + f) : o + T + (d === -2 ? l : f);
  }
  return [Ze(r, n + (r[t] || "<?>") + (e === 2 ? "</svg>" : e === 3 ? "</math>" : "")), i];
};
class K {
  constructor({ strings: e, _$litType$: t }, i) {
    let a;
    this.parts = [];
    let n = 0, s = 0;
    const l = e.length - 1, o = this.parts, [p, m] = dt(e, t);
    if (this.el = K.createElement(p, i), P.currentNode = this.el.content, t === 2 || t === 3) {
      const d = this.el.content.firstChild;
      d.replaceWith(...d.childNodes);
    }
    for (; (a = P.nextNode()) !== null && o.length < l; ) {
      if (a.nodeType === 1) {
        if (a.hasAttributes()) for (const d of a.getAttributeNames()) if (d.endsWith(He)) {
          const h = m[s++], f = a.getAttribute(d).split(T), y = /([.?@])?(.*)/.exec(h);
          o.push({ type: 1, index: n, name: y[2], strings: f, ctor: y[1] === "." ? pt : y[1] === "?" ? ht : y[1] === "@" ? gt : le }), a.removeAttribute(d);
        } else d.startsWith(T) && (o.push({ type: 6, index: n }), a.removeAttribute(d));
        if (qe.test(a.tagName)) {
          const d = a.textContent.split(T), h = d.length - 1;
          if (h > 0) {
            a.textContent = te ? te.emptyScript : "";
            for (let f = 0; f < h; f++) a.append(d[f], V()), P.nextNode(), o.push({ type: 2, index: ++n });
            a.append(d[h], V());
          }
        }
      } else if (a.nodeType === 8) if (a.data === Re) o.push({ type: 2, index: n });
      else {
        let d = -1;
        for (; (d = a.data.indexOf(T, d + 1)) !== -1; ) o.push({ type: 7, index: n }), d += T.length - 1;
      }
      n++;
    }
  }
  static createElement(e, t) {
    const i = M.createElement("template");
    return i.innerHTML = e, i;
  }
}
function q(r, e, t = r, i) {
  if (e === R) return e;
  let a = i !== void 0 ? t._$Co?.[i] : t._$Cl;
  const n = Y(e) ? void 0 : e._$litDirective$;
  return a?.constructor !== n && (a?._$AO?.(!1), n === void 0 ? a = void 0 : (a = new n(r), a._$AT(r, t, i)), i !== void 0 ? (t._$Co ??= [])[i] = a : t._$Cl = a), a !== void 0 && (e = q(r, a._$AS(r, e.values), a, i)), e;
}
class ut {
  constructor(e, t) {
    this._$AV = [], this._$AN = void 0, this._$AD = e, this._$AM = t;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(e) {
    const { el: { content: t }, parts: i } = this._$AD, a = (e?.creationScope ?? M).importNode(t, !0);
    P.currentNode = a;
    let n = P.nextNode(), s = 0, l = 0, o = i[0];
    for (; o !== void 0; ) {
      if (s === o.index) {
        let p;
        o.type === 2 ? p = new W(n, n.nextSibling, this, e) : o.type === 1 ? p = new o.ctor(n, o.name, o.strings, this, e) : o.type === 6 && (p = new mt(n, this, e)), this._$AV.push(p), o = i[++l];
      }
      s !== o?.index && (n = P.nextNode(), s++);
    }
    return P.currentNode = M, a;
  }
  p(e) {
    let t = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(e, i, t), t += i.strings.length - 2) : i._$AI(e[t])), t++;
  }
}
class W {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(e, t, i, a) {
    this.type = 2, this._$AH = g, this._$AN = void 0, this._$AA = e, this._$AB = t, this._$AM = i, this.options = a, this._$Cv = a?.isConnected ?? !0;
  }
  get parentNode() {
    let e = this._$AA.parentNode;
    const t = this._$AM;
    return t !== void 0 && e?.nodeType === 11 && (e = t.parentNode), e;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(e, t = this) {
    e = q(this, e, t), Y(e) ? e === g || e == null || e === "" ? (this._$AH !== g && this._$AR(), this._$AH = g) : e !== this._$AH && e !== R && this._(e) : e._$litType$ !== void 0 ? this.$(e) : e.nodeType !== void 0 ? this.T(e) : ct(e) ? this.k(e) : this._(e);
  }
  O(e) {
    return this._$AA.parentNode.insertBefore(e, this._$AB);
  }
  T(e) {
    this._$AH !== e && (this._$AR(), this._$AH = this.O(e));
  }
  _(e) {
    this._$AH !== g && Y(this._$AH) ? this._$AA.nextSibling.data = e : this.T(M.createTextNode(e)), this._$AH = e;
  }
  $(e) {
    const { values: t, _$litType$: i } = e, a = typeof i == "number" ? this._$AC(e) : (i.el === void 0 && (i.el = K.createElement(Ze(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === a) this._$AH.p(t);
    else {
      const n = new ut(a, this), s = n.u(this.options);
      n.p(t), this.T(s), this._$AH = n;
    }
  }
  _$AC(e) {
    let t = Pe.get(e.strings);
    return t === void 0 && Pe.set(e.strings, t = new K(e)), t;
  }
  k(e) {
    ye(this._$AH) || (this._$AH = [], this._$AR());
    const t = this._$AH;
    let i, a = 0;
    for (const n of e) a === t.length ? t.push(i = new W(this.O(V()), this.O(V()), this, this.options)) : i = t[a], i._$AI(n), a++;
    a < t.length && (this._$AR(i && i._$AB.nextSibling, a), t.length = a);
  }
  _$AR(e = this._$AA.nextSibling, t) {
    for (this._$AP?.(!1, !0, t); e !== this._$AB; ) {
      const i = ze(e).nextSibling;
      ze(e).remove(), e = i;
    }
  }
  setConnected(e) {
    this._$AM === void 0 && (this._$Cv = e, this._$AP?.(e));
  }
}
class le {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(e, t, i, a, n) {
    this.type = 1, this._$AH = g, this._$AN = void 0, this.element = e, this.name = t, this._$AM = a, this.options = n, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = g;
  }
  _$AI(e, t = this, i, a) {
    const n = this.strings;
    let s = !1;
    if (n === void 0) e = q(this, e, t, 0), s = !Y(e) || e !== this._$AH && e !== R, s && (this._$AH = e);
    else {
      const l = e;
      let o, p;
      for (e = n[0], o = 0; o < n.length - 1; o++) p = q(this, l[i + o], t, o), p === R && (p = this._$AH[o]), s ||= !Y(p) || p !== this._$AH[o], p === g ? e = g : e !== g && (e += (p ?? "") + n[o + 1]), this._$AH[o] = p;
    }
    s && !a && this.j(e);
  }
  j(e) {
    e === g ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, e ?? "");
  }
}
class pt extends le {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(e) {
    this.element[this.name] = e === g ? void 0 : e;
  }
}
class ht extends le {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(e) {
    this.element.toggleAttribute(this.name, !!e && e !== g);
  }
}
class gt extends le {
  constructor(e, t, i, a, n) {
    super(e, t, i, a, n), this.type = 5;
  }
  _$AI(e, t = this) {
    if ((e = q(this, e, t, 0) ?? g) === R) return;
    const i = this._$AH, a = e === g && i !== g || e.capture !== i.capture || e.once !== i.once || e.passive !== i.passive, n = e !== g && (i === g || a);
    a && this.element.removeEventListener(this.name, this, i), n && this.element.addEventListener(this.name, this, e), this._$AH = e;
  }
  handleEvent(e) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, e) : this._$AH.handleEvent(e);
  }
}
class mt {
  constructor(e, t, i) {
    this.element = e, this.type = 6, this._$AN = void 0, this._$AM = t, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(e) {
    q(this, e);
  }
}
const vt = be.litHtmlPolyfillSupport;
vt?.(K, W), (be.litHtmlVersions ??= []).push("3.3.3");
const ft = (r, e, t) => {
  const i = t?.renderBefore ?? e;
  let a = i._$litPart$;
  if (a === void 0) {
    const n = t?.renderBefore ?? null;
    i._$litPart$ = a = new W(e.insertBefore(V(), n), n, void 0, t ?? {});
  }
  return a._$AI(r), a;
};
const $e = globalThis;
class I extends N {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const e = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= e.firstChild, e;
  }
  update(e) {
    const t = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(e), this._$Do = ft(t, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return R;
  }
}
I._$litElement$ = !0, I.finalized = !0, $e.litElementHydrateSupport?.({ LitElement: I });
const _t = $e.litElementPolyfillSupport;
_t?.({ LitElement: I });
($e.litElementVersions ??= []).push("4.2.2");
const bt = {
  observing: {
    label: "Observe Only",
    icon: "◉",
    tone: "info",
    automationOff: !0
  },
  manual_idle: {
    label: "Manual Control — Automation Off",
    icon: "✋",
    tone: "neutral",
    automationOff: !0
  },
  shadow_qualifying: {
    label: "Shadow Qualifying",
    icon: "◌",
    tone: "info",
    automationOff: !1
  },
  shadow_ready: {
    label: "Shadow Ready",
    icon: "✓",
    tone: "positive",
    automationOff: !1
  },
  scheduled_idle: {
    label: "Scheduled Control",
    icon: "▶",
    tone: "positive",
    automationOff: !1
  },
  manual_override: {
    label: "Override",
    icon: "✋",
    tone: "warning",
    automationOff: !1
  },
  window_suspended: {
    label: "Suspended",
    icon: "▣",
    tone: "warning",
    automationOff: !1
  },
  safe_fallback: {
    label: "Safe Fallback",
    icon: "⚠",
    tone: "warning",
    automationOff: !1
  },
  emergency_protection: {
    label: "Emergency Protection",
    icon: "◆",
    tone: "critical",
    automationOff: !1
  },
  emergency_paused: {
    label: "Paused",
    icon: "Ⅱ",
    tone: "critical",
    automationOff: !1
  },
  degraded: {
    label: "Degraded",
    icon: "⚠",
    tone: "warning",
    automationOff: !1
  },
  reconciling: {
    label: "Reconciling",
    icon: "↻",
    tone: "info",
    automationOff: !1
  }
};
function yt(r) {
  return bt[r] ?? {
    label: r.replaceAll("_", " "),
    icon: "●",
    tone: "neutral",
    automationOff: !1
  };
}
function ie(r, e, t) {
  if (r === null)
    return "Unavailable";
  const i = e === "°F" ? r * 9 / 5 + 32 : r;
  return `${new Intl.NumberFormat(t, { maximumFractionDigits: 1 }).format(i)}${e}`;
}
function G(r, e, t) {
  return new Intl.DateTimeFormat(e, {
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    day: "numeric",
    ...t === void 0 ? {} : { timeZone: t }
  }).format(new Date(r));
}
function U(r) {
  return r.split("_").filter((e) => e.length > 0).map((e) => e.charAt(0).toUpperCase() + e.slice(1)).join(" ");
}
const w = 1, $t = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
], xt = /* @__PURE__ */ new Set([
  "none",
  "home",
  "away",
  "sleep",
  "vacation",
  "guest",
  "custom"
]);
class _ extends Error {
  constructor(e, t) {
    super(`${e}: ${t}`), this.name = "FrontendContractError";
  }
}
const wt = /* @__PURE__ */ new Set([
  "measured",
  "configured",
  "calculated",
  "forecast",
  "predicted",
  "planned"
]), kt = /* @__PURE__ */ new Set([
  "issue_code",
  "new_exclusion_reason",
  "new_hvac_mode",
  "new_quality",
  "new_state",
  "new_target_high_c",
  "new_target_low_c",
  "new_target_temperature_c",
  "previous_exclusion_reason",
  "previous_hvac_mode",
  "previous_quality",
  "previous_state",
  "previous_target_high_c",
  "previous_target_low_c",
  "previous_target_temperature_c"
]);
function v(r, e) {
  if (typeof r != "object" || r === null || Array.isArray(r))
    throw new _(e, "expected object");
  return r;
}
function k(r, e) {
  if (!Array.isArray(r))
    throw new _(e, "expected array");
  return r;
}
function u(r, e) {
  if (typeof r != "string" || r.length === 0)
    throw new _(e, "expected non-empty string");
  return r;
}
function Q(r, e) {
  return r === null ? null : u(r, e);
}
function $(r, e) {
  if (typeof r != "boolean")
    throw new _(e, "expected boolean");
  return r;
}
function H(r, e) {
  if (typeof r != "number" || !Number.isFinite(r))
    throw new _(e, "expected finite number");
  return r;
}
function x(r, e) {
  const t = H(r, e);
  if (!Number.isInteger(t) || t < 0)
    throw new _(e, "expected non-negative integer");
  return t;
}
function E(r, e) {
  return r === null ? null : H(r, e);
}
function b(r, e) {
  const t = u(r, e);
  if (!Number.isFinite(Date.parse(t)))
    throw new _(e, "expected ISO timestamp");
  return t;
}
function je(r, e) {
  const t = u(r, e);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t))
    throw new _(e, "expected YYYY-MM-DD local date");
  return t;
}
function Ge(r, e) {
  const t = u(r, e);
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(t))
    throw new _(e, "expected HH:MM local time");
  return t;
}
function z(r, e) {
  if (r.api_version !== w)
    throw new _(
      `${e}.api_version`,
      `expected ${String(w)}`
    );
}
function F(r, e) {
  return k(r, e).map(
    (t, i) => u(t, `${e}[${String(i)}]`)
  );
}
function pe(r, e) {
  const t = v(r, e), i = u(t.kind, `${e}.kind`);
  if (i !== "single" && i !== "range")
    throw new _(`${e}.kind`, "expected single or range");
  return {
    kind: i,
    target_c: E(t.target_c, `${e}.target_c`),
    heat_target_c: E(
      t.heat_target_c,
      `${e}.heat_target_c`
    ),
    cool_target_c: E(
      t.cool_target_c,
      `${e}.cool_target_c`
    )
  };
}
function St(r, e) {
  const t = v(r, e), i = u(t.occupancy_label, `${e}.occupancy_label`);
  if (!xt.has(i))
    throw new _(
      `${e}.occupancy_label`,
      "unsupported occupancy label"
    );
  return {
    period_id: u(t.period_id, `${e}.period_id`),
    local_start: Ge(t.local_start, `${e}.local_start`),
    label: typeof t.label == "string" ? t.label : u(t.label, `${e}.label`),
    occupancy_label: i,
    target: pe(t.target, `${e}.target`),
    tolerance_c: H(t.tolerance_c, `${e}.tolerance_c`)
  };
}
function zt(r, e) {
  const t = v(r, e), i = v(t.days, `${e}.days`), a = Object.fromEntries(
    $t.map((n) => [
      n,
      k(i[n], `${e}.days.${n}`).map(
        (s, l) => St(s, `${e}.days.${n}[${String(l)}]`)
      )
    ])
  );
  return {
    profile_id: u(t.profile_id, `${e}.profile_id`),
    name: u(t.name, `${e}.name`),
    enabled: $(t.enabled, `${e}.enabled`),
    days: a
  };
}
function Be(r, e) {
  const t = v(r, e);
  if (t.schedule_schema_version !== 1)
    throw new _(
      `${e}.schedule_schema_version`,
      "expected 1"
    );
  const i = v(t.zones, `${e}.zones`), a = {};
  for (const [n, s] of Object.entries(i)) {
    const l = `${e}.zones.${n}`, o = v(s, l);
    a[n] = {
      zone_id: u(o.zone_id, `${l}.zone_id`),
      enabled: $(o.enabled, `${l}.enabled`),
      selected_profile_id: u(
        o.selected_profile_id,
        `${l}.selected_profile_id`
      ),
      profiles: k(o.profiles, `${l}.profiles`).map(
        (p, m) => zt(p, `${l}.profiles[${String(m)}]`)
      )
    };
  }
  return {
    schedule_schema_version: 1,
    entry_id: u(t.entry_id, `${e}.entry_id`),
    equipment_group_id: u(
      t.equipment_group_id,
      `${e}.equipment_group_id`
    ),
    time_zone: u(t.time_zone, `${e}.time_zone`),
    revision: x(t.revision, `${e}.revision`),
    zones: a,
    saved_at_utc: b(t.saved_at_utc, `${e}.saved_at_utc`)
  };
}
function Ct(r) {
  const e = v(r, "schedule");
  return z(e, "schedule"), {
    api_version: w,
    revision: x(e.revision, "schedule.revision"),
    schedule: e.schedule === null ? null : Be(e.schedule, "schedule.schedule")
  };
}
function At(r) {
  const e = v(r, "schedule_validation");
  if (z(e, "schedule_validation"), e.valid !== !0)
    throw new _(
      "schedule_validation.valid",
      "expected true"
    );
  return {
    api_version: w,
    valid: !0,
    revision: x(
      e.revision,
      "schedule_validation.revision"
    )
  };
}
function Tt(r, e) {
  const t = v(r, e);
  return {
    zone_id: u(t.zone_id, `${e}.zone_id`),
    profile_id: u(t.profile_id, `${e}.profile_id`),
    period_id: u(t.period_id, `${e}.period_id`),
    target: pe(t.target, `${e}.target`),
    next_target: t.next_target === null ? null : pe(t.next_target, `${e}.next_target`),
    next_boundary_utc: b(
      t.next_boundary_utc,
      `${e}.next_boundary_utc`
    ),
    next_material_transition_utc: t.next_material_transition_utc === null ? null : b(
      t.next_material_transition_utc,
      `${e}.next_material_transition_utc`
    ),
    inherited_from_previous_day: $(
      t.inherited_from_previous_day,
      `${e}.inherited_from_previous_day`
    )
  };
}
function Et(r, e) {
  const t = v(r, e), i = u(t.kind, `${e}.kind`);
  if (i !== "gap" && i !== "fold")
    throw new _(`${e}.kind`, "expected gap or fold");
  return {
    zone_id: u(t.zone_id, `${e}.zone_id`),
    profile_id: u(t.profile_id, `${e}.profile_id`),
    period_id: u(t.period_id, `${e}.period_id`),
    local_date: je(t.local_date, `${e}.local_date`),
    local_start: Ge(t.local_start, `${e}.local_start`),
    kind: i,
    occurs_at_utc: b(t.occurs_at_utc, `${e}.occurs_at_utc`),
    explanation: u(t.explanation, `${e}.explanation`)
  };
}
function Dt(r) {
  const e = v(r, "schedule_preview");
  if (z(e, "schedule_preview"), e.authoritative !== !1)
    throw new _(
      "schedule_preview.authoritative",
      "preview must be nonauthoritative"
    );
  return {
    api_version: w,
    authoritative: !1,
    at_utc: b(e.at_utc, "schedule_preview.at_utc"),
    time_zone: u(e.time_zone, "schedule_preview.time_zone"),
    preview_week_start_local: je(
      e.preview_week_start_local,
      "schedule_preview.preview_week_start_local"
    ),
    zones: k(e.zones, "schedule_preview.zones").map(
      (t, i) => Tt(t, `schedule_preview.zones[${String(i)}]`)
    ),
    dst_warnings: k(
      e.dst_warnings,
      "schedule_preview.dst_warnings"
    ).map(
      (t, i) => Et(t, `schedule_preview.dst_warnings[${String(i)}]`)
    )
  };
}
function Pt(r) {
  const e = v(r, "schedule_save");
  return z(e, "schedule_save"), {
    api_version: w,
    revision: x(e.revision, "schedule_save.revision"),
    schedule: Be(e.schedule, "schedule_save.schedule")
  };
}
function It(r, e) {
  const t = v(r, e), i = (n, s) => k(n, s).map((l, o) => {
    const p = `${s}[${String(o)}]`, m = v(l, p);
    return {
      entity_id: u(m.entity_id, `${p}.entity_id`),
      enabled: $(m.enabled, `${p}.enabled`)
    };
  }), a = (n, s) => k(n, s).map((l, o) => {
    const p = `${s}[${String(o)}]`, m = v(l, p);
    return {
      entity_id: u(m.entity_id, `${p}.entity_id`),
      enabled: $(m.enabled, `${p}.enabled`),
      reviewed: $(m.reviewed, `${p}.reviewed`)
    };
  });
  return {
    ...t,
    zone_id: u(t.zone_id, `${e}.zone_id`),
    name: u(t.name, `${e}.name`),
    temperature_sources: i(
      t.temperature_sources,
      `${e}.temperature_sources`
    ),
    humidity_sources: i(
      t.humidity_sources,
      `${e}.humidity_sources`
    ),
    window_door_entity_ids: a(
      t.window_door_entity_ids,
      `${e}.window_door_entity_ids`
    ),
    occupancy_entity_ids: a(
      t.occupancy_entity_ids,
      `${e}.occupancy_entity_ids`
    ),
    stage_entity_ids: F(
      t.stage_entity_ids,
      `${e}.stage_entity_ids`
    ),
    fan_entity_ids: a(t.fan_entity_ids, `${e}.fan_entity_ids`)
  };
}
function Mt(r) {
  const e = v(r, "config");
  return z(e, "config"), {
    api_version: w,
    config: v(e.config, "config.config"),
    options: v(e.options, "config.options"),
    active_repairs: F(e.active_repairs, "config.active_repairs"),
    zones: k(e.zones, "config.zones").map(
      (t, i) => It(t, `config.zones[${String(i)}]`)
    )
  };
}
function Ut(r, e) {
  const t = v(r, e);
  return {
    zone_id: u(t.zone_id, `${e}.zone_id`),
    effective_temperature_c: E(
      t.effective_temperature_c,
      `${e}.effective_temperature_c`
    ),
    effective_humidity_pct: E(
      t.effective_humidity_pct,
      `${e}.effective_humidity_pct`
    ),
    thermostat_hvac_mode: Q(
      t.thermostat_hvac_mode,
      `${e}.thermostat_hvac_mode`
    ),
    supported_hvac_modes: F(
      t.supported_hvac_modes,
      `${e}.supported_hvac_modes`
    ),
    supports_single_target: $(
      t.supports_single_target,
      `${e}.supports_single_target`
    ),
    supports_target_range: $(
      t.supports_target_range,
      `${e}.supports_target_range`
    ),
    sensor_data_degraded: $(
      t.sensor_data_degraded,
      `${e}.sensor_data_degraded`
    ),
    thermostat_data_degraded: $(
      t.thermostat_data_degraded,
      `${e}.thermostat_data_degraded`
    )
  };
}
function Ie(r) {
  const e = v(r, "snapshot");
  return z(e, "snapshot"), {
    api_version: w,
    entry_id: u(e.entry_id, "snapshot.entry_id"),
    observation_revision: x(
      e.observation_revision,
      "snapshot.observation_revision"
    ),
    calculated_at_utc: b(
      e.calculated_at_utc,
      "snapshot.calculated_at_utc"
    ),
    control_state: u(e.control_state, "snapshot.control_state"),
    reason_code: Q(e.reason_code, "snapshot.reason_code"),
    zones: k(e.zones, "snapshot.zones").map(
      (t, i) => Ut(t, `snapshot.zones[${String(i)}]`)
    )
  };
}
function Ot(r, e) {
  const t = v(r, e);
  return {
    record_id: u(t.record_id, `${e}.record_id`),
    zone_id: Q(t.zone_id, `${e}.zone_id`),
    timestamp_utc: b(t.timestamp_utc, `${e}.timestamp_utc`),
    activity_type: u(t.activity_type, `${e}.activity_type`),
    reason_code: u(t.reason_code, `${e}.reason_code`),
    severity: u(t.severity, `${e}.severity`),
    explanation: u(t.explanation, `${e}.explanation`),
    detail: Lt(t.detail, `${e}.detail`)
  };
}
function Lt(r, e) {
  const t = v(r, e), i = {};
  for (const [a, n] of Object.entries(t)) {
    if (!kt.has(a))
      throw new _(
        `${e}.${a}`,
        "unexpected detail field"
      );
    if (n !== null && typeof n != "string" && typeof n != "number" && typeof n != "boolean")
      throw new _(
        `${e}.${a}`,
        "expected scalar detail"
      );
    if (typeof n == "number" && !Number.isFinite(n))
      throw new _(
        `${e}.${a}`,
        "expected finite detail"
      );
    i[a] = n;
  }
  return i;
}
function Nt(r) {
  const e = v(r, "activity");
  z(e, "activity");
  const t = u(e.order, "activity.order");
  if (t !== "newest" && t !== "oldest")
    throw new _(
      "activity.order",
      "expected newest or oldest"
    );
  return {
    api_version: w,
    total: x(e.total, "activity.total"),
    offset: x(e.offset, "activity.offset"),
    order: t,
    records: k(e.records, "activity.records").map(
      (i, a) => Ot(i, `activity.records[${String(a)}]`)
    )
  };
}
function Ht(r, e) {
  const t = v(r, e);
  return {
    ready: $(t.ready, `${e}.ready`),
    qualification_percent: H(
      t.qualification_percent,
      `${e}.qualification_percent`
    ),
    valid_evaluation_percent: H(
      t.valid_evaluation_percent,
      `${e}.valid_evaluation_percent`
    ),
    elapsed_hours: H(t.elapsed_hours, `${e}.elapsed_hours`),
    evaluated_decisions: x(
      t.evaluated_decisions,
      `${e}.evaluated_decisions`
    ),
    valid_evaluations: x(
      t.valid_evaluations,
      `${e}.valid_evaluations`
    ),
    minimum_material_transitions: x(
      t.minimum_material_transitions,
      `${e}.minimum_material_transitions`
    ),
    blocking_reasons: F(
      t.blocking_reasons,
      `${e}.blocking_reasons`
    ),
    blocking_faults: F(
      t.blocking_faults,
      `${e}.blocking_faults`
    )
  };
}
function Rt(r) {
  const e = v(r, "shadow");
  return z(e, "shadow"), {
    api_version: w,
    readiness: e.readiness === null ? null : Ht(e.readiness, "shadow.readiness"),
    history: k(e.history, "shadow.history").map((t, i) => {
      const a = `shadow.history[${String(i)}]`, n = v(t, a);
      return {
        safety_evaluation_id: u(
          n.safety_evaluation_id,
          `${a}.safety_evaluation_id`
        ),
        evaluated_at_utc: b(
          n.evaluated_at_utc,
          `${a}.evaluated_at_utc`
        ),
        outcome: u(n.outcome, `${a}.outcome`),
        reason_code: u(n.reason_code, `${a}.reason_code`),
        would_command: $(
          n.would_command,
          `${a}.would_command`
        )
      };
    })
  };
}
function qt(r) {
  const e = v(r, "observation");
  if (z(e, "observation"), e.model_ready_history_available !== !1)
    throw new _(
      "observation.model_ready_history_available",
      "Phase 2 must not claim model-ready history"
    );
  return {
    api_version: w,
    collection_active: $(
      e.collection_active,
      "observation.collection_active"
    ),
    observation_revision: x(
      e.observation_revision,
      "observation.observation_revision"
    ),
    calculated_at_utc: b(
      e.calculated_at_utc,
      "observation.calculated_at_utc"
    ),
    usable_temperature_sources: x(
      e.usable_temperature_sources,
      "observation.usable_temperature_sources"
    ),
    degraded_zone_count: x(
      e.degraded_zone_count,
      "observation.degraded_zone_count"
    ),
    presentation_history_hours: x(
      e.presentation_history_hours,
      "observation.presentation_history_hours"
    ),
    model_ready_history_available: !1,
    history_boundary: u(
      e.history_boundary,
      "observation.history_boundary"
    )
  };
}
function Ft(r, e) {
  const t = v(r, e);
  return {
    start_utc: b(t.start_utc, `${e}.start_utc`),
    end_utc: b(t.end_utc, `${e}.end_utc`)
  };
}
function Zt(r, e) {
  const t = v(r, e), i = t.value;
  if ((typeof i != "string" || i.length === 0) && (typeof i != "number" || !Number.isFinite(i)))
    throw new _(
      `${e}.value`,
      "expected finite number or text"
    );
  return {
    timestamp_utc: b(t.timestamp_utc, `${e}.timestamp_utc`),
    value: i
  };
}
function jt(r, e) {
  const t = v(r, e), i = u(t.value_kind, `${e}.value_kind`);
  if (!wt.has(i))
    throw new _(
      `${e}.value_kind`,
      "unsupported provenance"
    );
  if (i === "predicted" || i === "planned")
    throw new _(
      `${e}.value_kind`,
      "future Phase 3/4 series are not accepted by the Phase 2 panel"
    );
  return {
    kind: u(t.kind, `${e}.kind`),
    value_kind: i,
    unit: Q(t.unit, `${e}.unit`),
    source_quality: u(t.source_quality, `${e}.source_quality`),
    coverage_start_utc: b(
      t.coverage_start_utc,
      `${e}.coverage_start_utc`
    ),
    coverage_end_utc: b(
      t.coverage_end_utc,
      `${e}.coverage_end_utc`
    ),
    missing_intervals: k(
      t.missing_intervals,
      `${e}.missing_intervals`
    ).map(
      (a, n) => Ft(a, `${e}.missing_intervals[${String(n)}]`)
    ),
    samples: k(t.samples, `${e}.samples`).map(
      (a, n) => Zt(a, `${e}.samples[${String(n)}]`)
    )
  };
}
function Gt(r, e) {
  const t = v(r, e);
  return {
    annotation_id: u(t.annotation_id, `${e}.annotation_id`),
    timestamp_utc: b(t.timestamp_utc, `${e}.timestamp_utc`),
    reason_code: u(t.reason_code, `${e}.reason_code`),
    activity_record_id: u(
      t.activity_record_id,
      `${e}.activity_record_id`
    )
  };
}
function Bt(r) {
  const e = v(r, "timeline");
  if (z(e, "timeline"), e.indoor_prediction_available !== !1)
    throw new _(
      "timeline.indoor_prediction_available",
      "Phase 2 must not claim indoor prediction"
    );
  return {
    api_version: w,
    entry_id: u(e.entry_id, "timeline.entry_id"),
    zone_id: u(e.zone_id, "timeline.zone_id"),
    time_zone: u(e.time_zone, "timeline.time_zone"),
    local_date: u(e.local_date, "timeline.local_date"),
    day_start_utc: b(e.day_start_utc, "timeline.day_start_utc"),
    day_end_utc: b(e.day_end_utc, "timeline.day_end_utc"),
    generated_at_utc: b(
      e.generated_at_utc,
      "timeline.generated_at_utc"
    ),
    indoor_prediction_available: !1,
    capability_statement: u(
      e.capability_statement,
      "timeline.capability_statement"
    ),
    series: k(e.series, "timeline.series").map(
      (t, i) => jt(t, `timeline.series[${String(i)}]`)
    ),
    annotations: k(e.annotations, "timeline.annotations").map(
      (t, i) => Gt(t, `timeline.annotations[${String(i)}]`)
    )
  };
}
function Vt(r) {
  const e = v(r, "narrative");
  return z(e, "narrative"), {
    api_version: w,
    template_version: x(
      e.template_version,
      "narrative.template_version"
    ),
    entry_id: u(e.entry_id, "narrative.entry_id"),
    zone_id: u(e.zone_id, "narrative.zone_id"),
    control_state: u(e.control_state, "narrative.control_state"),
    reason_code: u(e.reason_code, "narrative.reason_code"),
    temperature_c: E(
      e.temperature_c,
      "narrative.temperature_c"
    ),
    hvac_action: Q(e.hvac_action, "narrative.hvac_action"),
    scheduled_target_c: E(
      e.scheduled_target_c,
      "narrative.scheduled_target_c"
    ),
    effective_target_c: E(
      e.effective_target_c,
      "narrative.effective_target_c"
    ),
    next_transition_utc: e.next_transition_utc === null ? null : b(
      e.next_transition_utc,
      "narrative.next_transition_utc"
    ),
    source_degraded: $(
      e.source_degraded,
      "narrative.source_degraded"
    ),
    context_forecast_available: $(
      e.context_forecast_available,
      "narrative.context_forecast_available"
    ),
    included_categories: F(
      e.included_categories,
      "narrative.included_categories"
    ),
    rendered: u(e.rendered, "narrative.rendered")
  };
}
class Yt {
  constructor(e, t) {
    if (this.hass = e, this.entryId = t, t.length === 0)
      throw new Error("entryId is required");
  }
  async request(e, t, i = {}) {
    const a = await this.hass.callWS({
      type: e,
      api_version: w,
      entry_id: this.entryId,
      ...i
    });
    return t(a);
  }
  configuration() {
    return this.request(
      "intelligent_climate/config/get",
      Mt
    );
  }
  snapshot() {
    return this.request("intelligent_climate/snapshot/get", Ie);
  }
  activity(e = 0, t = 100, i = "newest") {
    return this.request("intelligent_climate/activity/list", Nt, {
      offset: e,
      limit: t,
      order: i
    });
  }
  shadowStatus() {
    return this.request(
      "intelligent_climate/shadow/status",
      Rt
    );
  }
  observationStatus() {
    return this.request(
      "intelligent_climate/observation/status",
      qt
    );
  }
  todayTimeline(e) {
    return this.request(
      "intelligent_climate/timeline/today",
      Bt,
      { zone_id: e }
    );
  }
  narrative(e) {
    return this.request(
      "intelligent_climate/narrative/current",
      Vt,
      { zone_id: e }
    );
  }
  schedule() {
    return this.request(
      "intelligent_climate/schedule/get",
      Ct
    );
  }
  validateSchedule(e) {
    return this.request(
      "intelligent_climate/schedule/validate",
      At,
      { schedule: e }
    );
  }
  previewSchedule(e, t) {
    return this.request(
      "intelligent_climate/schedule/preview",
      Dt,
      t === void 0 ? { schedule: e } : { schedule: e, at_utc: t }
    );
  }
  saveSchedule(e, t) {
    return this.request(
      "intelligent_climate/schedule/save",
      Pt,
      { schedule: e, expected_revision: t }
    );
  }
  async dashboardData() {
    const [e, t, i, a, n] = await Promise.all([
      this.configuration(),
      this.snapshot(),
      this.activity(),
      this.shadowStatus(),
      this.observationStatus()
    ]);
    return { configuration: e, snapshot: t, activity: i, shadow: a, observation: n };
  }
  async subscribe(e) {
    return this.hass.connection.subscribeMessage(
      (t) => e(Ie(t)),
      {
        type: "intelligent_climate/subscribe",
        api_version: w,
        entry_id: this.entryId
      }
    );
  }
}
const Ve = se`
  :host {
    color: var(--primary-text-color, #1f2937);
    background: var(
      --lovelace-background,
      var(--primary-background-color, #f4f6f8)
    );
    font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
    color-scheme: light dark;
    --ic-surface: var(--card-background-color, #ffffff);
    --ic-surface-muted: color-mix(
      in srgb,
      var(--secondary-background-color, #eef1f4) 82%,
      transparent
    );
    --ic-border: color-mix(
      in srgb,
      var(--divider-color, #d8dde3) 86%,
      transparent
    );
    --ic-accent: var(--primary-color, #03a9f4);
    --ic-radius: 18px;
    --ic-shadow: 0 8px 24px rgb(0 0 0 / 8%);
  }

  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }

  button,
  select,
  a {
    min-block-size: 44px;
  }

  button,
  select {
    color: inherit;
    font: inherit;
  }

  :focus-visible {
    outline: 3px solid color-mix(in srgb, var(--ic-accent) 75%, white);
    outline-offset: 3px;
  }

  .sr-only {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      scroll-behavior: auto !important;
      transition-duration: 0.01ms !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
    }
  }
`;
function Ye(r = globalThis.crypto) {
  if (typeof r.randomUUID == "function")
    return r.randomUUID();
  const e = r.getRandomValues(new Uint8Array(16));
  e[6] = (e[6] ?? 0) & 15 | 64, e[8] = (e[8] ?? 0) & 63 | 128;
  const t = Array.from(
    e,
    (i) => i.toString(16).padStart(2, "0")
  );
  return `${t.slice(0, 4).join("")}-${t.slice(4, 6).join("")}-${t.slice(6, 8).join("")}-${t.slice(8, 10).join("")}-${t.slice(10).join("")}`;
}
const O = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
], S = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday"
}, Kt = {
  homeHeatC: 20.6,
  homeCoolC: 23.9,
  awayHeatC: 18.9,
  awayCoolC: 26.7,
  sleepHeatC: 19.4,
  sleepCoolC: 23.9
}, ae = class ae extends I {
  constructor() {
    super(...arguments), this.zoneSnapshots = [], this.validationMessage = "", this.saving = !1, this.dirty = !1, this.temperatureUnit = "°C", this.locale = "en-US", this.selectedZoneId = "", this.selectedProfileId = "", this.mobileDay = "monday", this.copySource = "monday", this.copyTargets = [], this.starterTargets = { ...Kt }, this.zoneChanged = (e) => {
      const t = e.currentTarget;
      if (!(t instanceof HTMLSelectElement)) return;
      this.selectedZoneId = t.value;
      const i = this.currentZone();
      this.selectedProfileId = i?.selected_profile_id ?? "";
    }, this.profileChanged = (e) => {
      const t = e.currentTarget;
      if (!(t instanceof HTMLSelectElement)) return;
      this.selectedProfileId = t.value;
      const i = this.selectedZoneId;
      this.updateDocument((a) => {
        const n = a.zones[i];
        n !== void 0 && (n.selected_profile_id = t.value);
      });
    }, this.zoneEnabledChanged = (e) => {
      const t = e.currentTarget;
      if (!(t instanceof HTMLInputElement)) return;
      const i = this.selectedZoneId;
      this.updateDocument((a) => {
        const n = a.zones[i];
        n !== void 0 && (n.enabled = t.checked);
      });
    }, this.profileEnabledChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLInputElement && this.updateProfile((i) => i.enabled = t.checked);
    }, this.mobileDayChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLSelectElement && (this.mobileDay = t.value, this.copySource = this.mobileDay, this.copyTargets = this.copyTargets.filter(
        (i) => i !== this.copySource
      ));
    }, this.cancelClearDay = () => {
      this.clearPendingDay = void 0;
    }, this.copySourceChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLSelectElement && (this.copySource = t.value, this.copyTargets = this.copyTargets.filter(
        (i) => i !== this.copySource
      ));
    }, this.copyDay = () => {
      const e = this.copySource, t = [...this.copyTargets];
      this.updateProfile((i) => {
        const a = i.days[e];
        for (const n of t)
          i.days[n] = a.map((s) => ({
            ...structuredClone(s),
            period_id: this.uuid()
          }));
      }), this.copyTargets = [];
    }, this.requestPreview = () => {
      this.dispatchEvent(
        new CustomEvent("schedule-preview", { bubbles: !0, composed: !0 })
      );
    }, this.requestSave = () => {
      this.dispatchEvent(
        new CustomEvent("schedule-save", { bubbles: !0, composed: !0 })
      );
    };
  }
  willUpdate(e) {
    if (e.has("document")) {
      const t = Object.keys(this.document.zones);
      t.includes(this.selectedZoneId) || (this.selectedZoneId = t[0] ?? "");
      const i = this.document.zones[this.selectedZoneId];
      i !== void 0 && !i.profiles.some(
        (a) => a.profile_id === this.selectedProfileId
      ) && (this.selectedProfileId = i.selected_profile_id);
    }
  }
  render() {
    const e = this.currentZone(), t = this.currentProfile();
    return e === void 0 || t === void 0 ? c`<p role="status">No schedule zone is available.</p>` : c`
      <section class="editor-toolbar" aria-label="Schedule selection">
        <label>
          <span>Zone</span>
          <select .value=${this.selectedZoneId} @change=${this.zoneChanged}>
            ${Object.keys(this.document.zones).map(
      (i) => c`<option value=${i}>${this.zoneName(i)}</option>`
    )}
          </select>
        </label>
        ${e.profiles.length === 1 ? c`<div class="profile-summary">
                <span>Schedule profile</span>
                <strong>${t.name}</strong>
                <small>
                  A profile is a complete weekly schedule. Additional profiles
                  can later support patterns such as Vacation or Guest.
                </small>
              </div>` : c`<label>
                <span>Schedule profile</span>
                <select
                  .value=${this.selectedProfileId}
                  @change=${this.profileChanged}
                  aria-describedby="profile-help"
                >
                  ${e.profiles.map(
      (i) => c`<option value=${i.profile_id}>
                        ${i.name}
                      </option>`
    )}
                </select>
                <small id="profile-help">
                  Each profile is a complete weekly schedule for this zone.
                </small>
              </label>`}
        <label class="switch-label">
          <input
            type="checkbox"
            .checked=${e.enabled}
            @change=${this.zoneEnabledChanged}
          />
          <span>Schedule this zone</span>
        </label>
        <label class="switch-label">
          <input
            type="checkbox"
            .checked=${t.enabled}
            @change=${this.profileEnabledChanged}
          />
          <span>Enable profile</span>
        </label>
      </section>

      ${this.renderModeGuidance()}

      <section class="template-tools" aria-labelledby="template-heading">
        <div class="template-intro">
          <h3 id="template-heading">Starter schedule</h3>
          <p>
            Review these comfort bands before replacing the matching days.
            Heating and cooling targets stay together in one schedule period;
            your thermostat mode determines which side applies.
          </p>
        </div>
        <div class="starter-grid">
          ${this.starterTargetInputs("Home", "homeHeatC", "homeCoolC")}
          ${this.starterTargetInputs("Away", "awayHeatC", "awayCoolC")}
          ${this.starterTargetInputs("Sleep", "sleepHeatC", "sleepCoolC")}
        </div>
        <div class="template-actions">
          <button type="button" @click=${() => this.applyTemplate("weekday")}>
            Apply weekdays
          </button>
          <button type="button" @click=${() => this.applyTemplate("weekend")}>
            Apply weekend
          </button>
        </div>
      </section>

      <label class="mobile-day-picker">
        <span>Day to edit</span>
        <select .value=${this.mobileDay} @change=${this.mobileDayChanged}>
          ${O.map(
      (i) => c`<option value=${i}>${S[i]}</option>`
    )}
        </select>
      </label>

      <section class="week-grid" aria-label="Weekly schedule">
        ${O.map((i) => this.renderDay(t, i))}
      </section>

      <section
        class="copy-tool"
        id="copy-day-tool"
        aria-labelledby="copy-heading"
      >
        <div>
          <h3 id="copy-heading">Copy a day</h3>
          <p>
            Choose any source and one or more destinations. Copied periods
            receive new stable identities.
          </p>
        </div>
        <label>
          <span>Copy from</span>
          <select .value=${this.copySource} @change=${this.copySourceChanged}>
            ${O.map(
      (i) => c`<option value=${i}>${S[i]}</option>`
    )}
          </select>
        </label>
        <div class="copy-days">
          ${O.filter((i) => i !== this.copySource).map(
      (i) => c`<label>
                <input
                  type="checkbox"
                  aria-label=${`Copy ${S[this.copySource]} to ${S[i]}`}
                  .checked=${this.copyTargets.includes(i)}
                  @change=${(a) => this.copyTargetChanged(i, a)}
                />
                ${S[i]}
              </label>`
    )}
        </div>
        <button
          type="button"
          class="secondary"
          ?disabled=${this.copyTargets.length === 0}
          @click=${this.copyDay}
        >
          Copy to selected days
        </button>
      </section>

      ${this.renderPreview(e)}

      <section class="save-bar ${this.dirty ? "dirty" : ""}">
        <div>
          <strong
            >${this.dirty ? "Unsaved schedule changes" : "Schedule is saved"}</strong
          >
          <span
            >Revision ${this.document.revision} ·
            ${this.document.time_zone}</span
          >
        </div>
        <button type="button" @click=${this.requestPreview}>Preview</button>
        <button
          type="button"
          class="primary"
          ?disabled=${!this.dirty || this.saving}
          @click=${this.requestSave}
        >
          ${this.saving ? "Saving…" : "Validate & save"}
        </button>
      </section>
      ${this.validationMessage.length === 0 ? g : c`<div class="validation" role="alert">
              <strong>Schedule needs attention</strong>
              <p>${this.validationMessage}</p>
            </div>`}
    `;
  }
  renderDay(e, t) {
    const i = e.days[t], a = t === this.mobileDay ? "" : "mobile-hidden";
    return c`<article class="day-column ${a}">
      <header>
        <div>
          <h3>${S[t]}</h3>
          <span
            >${i.length}
            ${i.length === 1 ? "period" : "periods"}</span
          >
        </div>
        <div class="day-actions">
          <button
            type="button"
            aria-label=${`Copy ${S[t]}`}
            @click=${() => this.selectCopySource(t)}
          >
            Copy
          </button>
          <button
            type="button"
            class="add"
            aria-label=${`Add ${S[t]} period`}
            @click=${() => this.addPeriod(t)}
          >
            + Add
          </button>
          <button
            type="button"
            class="danger"
            ?disabled=${i.length === 0}
            aria-label=${`Clear ${S[t]}`}
            @click=${() => this.requestClearDay(t)}
          >
            Clear
          </button>
        </div>
      </header>
      ${this.clearPendingDay === t ? c`<div class="clear-confirmation" role="alert">
              <p>
                Clear every ${S[t]} period? The final settings from
                the prior configured day will continue until the next period.
              </p>
              <div>
                <button type="button" @click=${this.cancelClearDay}>
                  Cancel
                </button>
                <button
                  type="button"
                  class="danger"
                  aria-label=${`Confirm clear ${S[t]}`}
                  @click=${() => this.confirmClearDay(t)}
                >
                  Clear ${S[t]}
                </button>
              </div>
            </div>` : g}
      ${i.length === 0 ? c`<p class="inheritance">
              ↺ Inherits the most recent period from an earlier day.
            </p>` : i[0]?.local_start === "00:00" ? g : c`<p class="inheritance">
                ↺ Midnight–${i[0]?.local_start}: previous period remains
                active.
              </p>`}
      <ol>
        ${i.map((n, s) => this.renderPeriod(t, n, s))}
      </ol>
    </article>`;
  }
  renderPeriod(e, t, i) {
    const a = this.preview?.zones.some(
      (l) => l.period_id === t.period_id
    ), n = `days.${e}[${String(i)}]`, s = this.validationMessage.includes(n);
    return c`<li
      class="period ${a ? "current" : ""} ${s ? "invalid" : ""}"
    >
      <div class="period-heading">
        <strong
          >${a ? "● Current period" : `Period ${String(i + 1)}`}</strong
        >
        <div>
          <button
            type="button"
            aria-label=${`Duplicate ${S[e]} period ${String(i + 1)}`}
            @click=${() => this.duplicatePeriod(e, i)}
          >
            Duplicate
          </button>
          <button
            type="button"
            class="danger"
            aria-label=${`Delete ${S[e]} period ${String(i + 1)}`}
            @click=${() => this.deletePeriod(e, i)}
          >
            Delete
          </button>
        </div>
      </div>
      <div class="field-grid">
        <label>
          <span>Starts</span>
          <input
            type="time"
            .value=${t.local_start}
            @change=${(l) => this.periodTextChanged(e, i, "local_start", l)}
          />
        </label>
        <label>
          <span>Label</span>
          <input
            type="text"
            maxlength="64"
            .value=${t.label}
            @input=${(l) => this.periodTextChanged(e, i, "label", l)}
          />
        </label>
        <label>
          <span>Occupancy label</span>
          <select
            .value=${t.occupancy_label}
            @change=${(l) => this.periodTextChanged(e, i, "occupancy_label", l)}
          >
            ${[
      "none",
      "home",
      "away",
      "sleep",
      "vacation",
      "guest",
      "custom"
    ].map(
      (l) => c`<option value=${l}>${this.titleCase(l)}</option>`
    )}
          </select>
        </label>
        <label>
          <span>Target type</span>
          <select
            .value=${t.target.kind}
            @change=${(l) => this.targetKindChanged(e, i, l)}
          >
            <option value="single">Single target</option>
            <option value="range">Heat / cool range</option>
          </select>
        </label>
        ${t.target.kind === "single" ? this.temperatureInput(
      e,
      i,
      "target_c",
      "Target",
      t.target.target_c
    ) : c`${this.temperatureInput(e, i, "heat_target_c", "Heat target", t.target.heat_target_c)}
              ${this.temperatureInput(e, i, "cool_target_c", "Cool target", t.target.cool_target_c)}`}
        <label>
          <span>Tolerance (${this.temperatureUnit})</span>
          <input
            type="number"
            min=${this.temperatureUnit === "°F" ? "0.2" : "0.1"}
            max=${this.temperatureUnit === "°F" ? "5" : "2.8"}
            step=${this.temperatureUnit === "°F", "0.1"}
            .value=${this.formatNumber(this.displayDelta(t.tolerance_c))}
            @change=${(l) => this.toleranceChanged(e, i, l)}
          />
        </label>
      </div>
      ${this.targetModeWarning(t)}
      ${s ? c`<p class="field-error">Review this period and the validation summary.</p>` : g}
    </li>`;
  }
  temperatureInput(e, t, i, a, n) {
    return c`<label>
      <span>${a} (${this.temperatureUnit})</span>
      <input
        type="number"
        step=${this.temperatureUnit === "°F" ? "0.5" : "0.1"}
        .value=${n === null ? "" : this.formatNumber(this.displayTemperature(n))}
        @change=${(s) => this.targetValueChanged(e, t, i, s)}
      />
    </label>`;
  }
  renderPreview(e) {
    const t = this.preview;
    if (t === void 0)
      return c`<section class="preview-card">
        <h3>Authoritative preview</h3>
        <p>
          Preview the unsaved draft to see the current target, next material
          transition, inheritance, and exact DST behavior.
        </p>
      </section>`;
    const i = t.zones.find(
      (n) => n.zone_id === e.zone_id
    ), a = t.dst_warnings.filter(
      (n) => n.zone_id === e.zone_id
    );
    return c`<section class="preview-card" aria-labelledby="preview-heading">
      <div>
        <h3 id="preview-heading">Authoritative preview</h3>
        <span
          >Week of ${t.preview_week_start_local} ·
          ${t.time_zone}</span
        >
      </div>
      ${i === void 0 ? c`<p>
              This zone is disabled, so it has no active scheduled target.
            </p>` : c`<dl>
              <div>
                <dt>Current target</dt>
                <dd>${this.targetText(i.target)}</dd>
              </div>
              <div>
                <dt>Next target</dt>
                <dd>
                  ${i.next_target === null ? "No material change" : this.targetText(i.next_target)}
                </dd>
              </div>
              <div>
                <dt>Next transition</dt>
                <dd>
                  ${i.next_material_transition_utc === null ? "None" : this.dateTime(i.next_material_transition_utc)}
                </dd>
              </div>
              <div>
                <dt>Inherited now</dt>
                <dd>
                  ${i.inherited_from_previous_day ? "Yes — from an earlier day" : "No"}
                </dd>
              </div>
            </dl>`}
      ${a.length === 0 ? c`<p class="no-warning">
              ✓ No scheduled boundary crosses a DST gap or repeated hour in this
              preview week.
            </p>` : c`<ul class="dst-warnings">
              ${a.map(
      (n) => c`<li>
                    <strong
                      >${n.kind === "gap" ? "Spring-forward gap" : "Repeated-hour fold"}</strong
                    >
                    <span>${n.explanation}</span>
                  </li>`
    )}
            </ul>`}
      <p class="preview-boundary">
        Preview is unsaved and nonauthoritative for control.
      </p>
    </section>`;
  }
  currentZone() {
    return this.document.zones[this.selectedZoneId];
  }
  currentProfile() {
    return this.currentZone()?.profiles.find(
      (t) => t.profile_id === this.selectedProfileId
    );
  }
  updateDocument(e) {
    const t = structuredClone(this.document);
    e(t), this.dispatchEvent(
      new CustomEvent("schedule-change", {
        detail: { document: t },
        bubbles: !0,
        composed: !0
      })
    );
  }
  updateProfile(e) {
    const t = this.selectedZoneId, i = this.selectedProfileId;
    this.updateDocument((a) => {
      const n = a.zones[t]?.profiles.find(
        (s) => s.profile_id === i
      );
      n !== void 0 && e(n);
    });
  }
  addPeriod(e) {
    this.updateProfile((t) => {
      const i = t.days[e];
      i.push(this.newPeriod(this.nextAvailableTime(i))), i.sort(
        (a, n) => a.local_start.localeCompare(n.local_start)
      );
    });
  }
  duplicatePeriod(e, t) {
    this.updateProfile((i) => {
      const a = i.days[e][t];
      a !== void 0 && (i.days[e].push({
        ...structuredClone(a),
        period_id: this.uuid(),
        local_start: this.nextAvailableTime(
          i.days[e],
          a.local_start
        )
      }), i.days[e].sort(
        (n, s) => n.local_start.localeCompare(s.local_start)
      ));
    });
  }
  deletePeriod(e, t) {
    this.updateProfile((i) => i.days[e].splice(t, 1));
  }
  requestClearDay(e) {
    this.clearPendingDay = e;
  }
  confirmClearDay(e) {
    this.updateProfile((t) => {
      t.days[e] = [];
    }), this.clearPendingDay = void 0;
  }
  periodTextChanged(e, t, i, a) {
    const n = a.currentTarget;
    (n instanceof HTMLInputElement || n instanceof HTMLSelectElement) && this.updateProfile((s) => {
      const l = s.days[e][t];
      l !== void 0 && (i === "occupancy_label" ? l.occupancy_label = n.value : l[i] = n.value, s.days[e].sort(
        (o, p) => o.local_start.localeCompare(p.local_start)
      ));
    });
  }
  targetKindChanged(e, t, i) {
    const a = i.currentTarget;
    a instanceof HTMLSelectElement && this.updateProfile((n) => {
      const s = n.days[e][t];
      s !== void 0 && (s.target = a.value === "range" ? {
        kind: "range",
        target_c: null,
        heat_target_c: 20,
        cool_target_c: 24
      } : {
        kind: "single",
        target_c: 22,
        heat_target_c: null,
        cool_target_c: null
      });
    });
  }
  targetValueChanged(e, t, i, a) {
    const n = a.currentTarget;
    if (!(n instanceof HTMLInputElement) || n.value.length === 0)
      return;
    const s = Number(n.value);
    Number.isFinite(s) && this.updateProfile((l) => {
      const o = l.days[e][t];
      o !== void 0 && i !== "kind" && (o.target[i] = this.celsiusTemperature(s));
    });
  }
  toleranceChanged(e, t, i) {
    const a = i.currentTarget;
    if (!(a instanceof HTMLInputElement)) return;
    const n = Number(a.value);
    Number.isFinite(n) && this.updateProfile((s) => {
      const l = s.days[e][t];
      l !== void 0 && (l.tolerance_c = this.celsiusDelta(n));
    });
  }
  copyTargetChanged(e, t) {
    const i = t.currentTarget;
    i instanceof HTMLInputElement && (this.copyTargets = i.checked ? [...this.copyTargets, e] : this.copyTargets.filter((a) => a !== e));
  }
  selectCopySource(e) {
    this.copySource = e, this.copyTargets = this.copyTargets.filter((i) => i !== e);
    const t = this.renderRoot.querySelector("#copy-day-tool");
    t !== null && typeof t.scrollIntoView == "function" && t.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  applyTemplate(e) {
    const t = e === "weekday" ? O.slice(0, 5) : O.slice(5), i = e === "weekday" ? [
      ["06:30", "Morning", "homeHeatC", "homeCoolC"],
      ["08:30", "Away", "awayHeatC", "awayCoolC"],
      ["17:30", "Evening", "homeHeatC", "homeCoolC"],
      ["22:30", "Sleep", "sleepHeatC", "sleepCoolC"]
    ] : [
      ["08:00", "Morning", "homeHeatC", "homeCoolC"],
      ["23:00", "Sleep", "sleepHeatC", "sleepCoolC"]
    ];
    this.updateProfile((a) => {
      for (const n of t)
        a.days[n] = i.map(([s, l, o, p]) => ({
          ...this.newPeriod(s),
          label: l,
          occupancy_label: l === "Sleep" ? "sleep" : l === "Away" ? "away" : "home",
          target: {
            kind: "range",
            target_c: null,
            heat_target_c: this.starterTargets[o],
            cool_target_c: this.starterTargets[p]
          }
        }));
    });
  }
  starterTargetInputs(e, t, i) {
    return c`<fieldset>
      <legend>${e}</legend>
      ${this.starterTemperatureInput("Heat", t)}
      ${this.starterTemperatureInput("Cool", i)}
    </fieldset>`;
  }
  starterTemperatureInput(e, t) {
    return c`<label>
      <span>${e} (${this.temperatureUnit})</span>
      <input
        type="number"
        step=${this.temperatureUnit === "°F" ? "0.5" : "0.1"}
        .value=${this.formatNumber(
      this.displayTemperature(this.starterTargets[t])
    )}
        @change=${(i) => this.starterTargetChanged(t, i)}
      />
    </label>`;
  }
  starterTargetChanged(e, t) {
    const i = t.currentTarget;
    if (!(i instanceof HTMLInputElement)) return;
    const a = Number(i.value);
    Number.isFinite(a) && (this.starterTargets = {
      ...this.starterTargets,
      [e]: this.celsiusTemperature(a)
    });
  }
  newPeriod(e) {
    return {
      period_id: this.uuid(),
      local_start: e,
      label: "",
      occupancy_label: "none",
      target: this.defaultTarget(),
      tolerance_c: 0.5
    };
  }
  nextAvailableTime(e, t = "05:30") {
    const i = new Set(e.map((n) => n.local_start));
    let a = this.timeMinutes(t) + 30;
    for (let n = 0; n < 48; n += 1) {
      a %= 1440;
      const s = `${String(Math.floor(a / 60)).padStart(2, "0")}:${String(a % 60).padStart(2, "0")}`;
      if (!i.has(s)) return s;
      a += 30;
    }
    return "00:00";
  }
  timeMinutes(e) {
    const [t = "0", i = "0"] = e.split(":");
    return Number(t) * 60 + Number(i);
  }
  uuid() {
    return Ye();
  }
  zoneName(e) {
    return this.zones.find((t) => t.zone_id === e)?.name ?? e;
  }
  currentZoneSnapshot() {
    return this.zoneSnapshots.find(
      (e) => e.zone_id === this.selectedZoneId
    );
  }
  defaultTarget() {
    return this.currentZoneSnapshot()?.supports_target_range === !0 ? {
      kind: "range",
      target_c: null,
      heat_target_c: this.starterTargets.homeHeatC,
      cool_target_c: this.starterTargets.homeCoolC
    } : {
      kind: "single",
      target_c: 22,
      heat_target_c: null,
      cool_target_c: null
    };
  }
  renderModeGuidance() {
    const t = this.currentZoneSnapshot()?.thermostat_hvac_mode, i = t == null ? "Unavailable" : this.modeLabel(t);
    let a;
    return t === "heat_cool" || t === "auto" ? a = "Use heat / cool ranges. A single target is ambiguous in this mode and Scheduled Control will remain blocked for that period." : t === "heat" ? a = "A single target is interpreted as heating. A heat / cool range requires Heat/Cool or Auto mode before Scheduled Control can use it." : t === "cool" ? a = "A single target is interpreted as cooling. A heat / cool range requires Heat/Cool or Auto mode before Scheduled Control can use it." : t === "off" ? a = "Schedules remain editable, but Scheduled Control is blocked while the thermostat is Off." : a = "Schedules remain editable, but Scheduled Control is blocked until the thermostat reports an unambiguous Heat, Cool, or Heat/Cool mode.", c`<section
      class="mode-guidance"
      aria-labelledby="mode-guidance-heading"
    >
      <div>
        <span>Current thermostat mode</span>
        <strong id="mode-guidance-heading">${i}</strong>
      </div>
      <p>${a}</p>
      <small>The schedule never changes HVAC mode automatically.</small>
    </section>`;
  }
  targetModeWarning(e) {
    const t = this.currentZoneSnapshot(), i = t?.thermostat_hvac_mode;
    if (!(e.target.kind === "single" ? t?.supports_single_target === !0 : t?.supports_target_range === !0)) {
      const o = e.target.kind === "single" ? "Single targets are" : "Heat / cool ranges are";
      return c`<p class="mode-warning" role="status">
        ${o} not supported by the current command-authority
        thermostat. This period remains visible, but it cannot be used for
        Scheduled Control.
      </p>`;
    }
    if (e.target.kind === "single" && (i === "heat" || i === "cool") || e.target.kind === "range" && (i === "heat_cool" || i === "auto")) return g;
    const s = e.target.kind === "single" ? "Single target" : "Heat / cool range", l = i == null ? "an unavailable mode" : this.modeLabel(i);
    return c`<p class="mode-warning" role="status">
      ${s} cannot be used for Scheduled Control while the thermostat
      reports ${l}. It remains saved and visible; control will fail
      closed.
    </p>`;
  }
  modeLabel(e) {
    return e === "heat_cool" ? "Heat/Cool" : e === "auto" ? "Auto" : this.titleCase(e);
  }
  displayTemperature(e) {
    return this.temperatureUnit === "°F" ? e * 9 / 5 + 32 : e;
  }
  celsiusTemperature(e) {
    return this.temperatureUnit === "°F" ? (e - 32) * 5 / 9 : e;
  }
  displayDelta(e) {
    return this.temperatureUnit === "°F" ? e * 9 / 5 : e;
  }
  celsiusDelta(e) {
    return this.temperatureUnit === "°F" ? e * 5 / 9 : e;
  }
  formatNumber(e) {
    return String(Math.round(e * 10) / 10);
  }
  targetText(e) {
    return e.kind === "single" && e.target_c !== null ? `${this.formatNumber(this.displayTemperature(e.target_c))}${this.temperatureUnit}` : e.heat_target_c !== null && e.cool_target_c !== null ? `${this.formatNumber(this.displayTemperature(e.heat_target_c))}–${this.formatNumber(this.displayTemperature(e.cool_target_c))}${this.temperatureUnit}` : "Unavailable";
  }
  dateTime(e) {
    return new Intl.DateTimeFormat(this.locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: this.document.time_zone
    }).format(new Date(e));
  }
  titleCase(e) {
    return e.charAt(0).toUpperCase() + e.slice(1);
  }
};
ae.properties = {
  document: { attribute: !1 },
  zones: { attribute: !1 },
  zoneSnapshots: { attribute: !1 },
  preview: { attribute: !1 },
  validationMessage: { type: String },
  saving: { type: Boolean },
  dirty: { type: Boolean },
  temperatureUnit: { type: String },
  locale: { type: String },
  selectedZoneId: { state: !0 },
  selectedProfileId: { state: !0 },
  mobileDay: { state: !0 },
  copySource: { state: !0 },
  copyTargets: { state: !0 },
  clearPendingDay: { state: !0 },
  starterTargets: { state: !0 }
}, ae.styles = [
  Ve,
  se`
      :host {
        display: block;
      }
      button,
      input,
      select {
        min-block-size: 44px;
        font: inherit;
      }
      button {
        border: 1px solid var(--ic-border);
        border-radius: 10px;
        background: var(--ic-surface);
        color: var(--primary-text-color);
        padding: 8px 12px;
        cursor: pointer;
      }
      button:hover {
        border-color: var(--ic-accent);
      }
      button:focus-visible,
      input:focus-visible,
      select:focus-visible {
        outline: 3px solid color-mix(in srgb, var(--ic-accent) 45%, transparent);
        outline-offset: 2px;
      }
      button.primary {
        background: var(--ic-accent);
        color: white;
        border-color: var(--ic-accent);
        font-weight: 700;
      }
      button.danger {
        color: var(--error-color, #c62828);
      }
      button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      label {
        display: grid;
        gap: 5px;
        font-size: 0.84rem;
        font-weight: 650;
      }
      input,
      select {
        box-sizing: border-box;
        inline-size: 100%;
        padding: 8px 10px;
        border: 1px solid var(--ic-border);
        border-radius: 9px;
        background: var(--ic-surface);
        color: var(--primary-text-color);
      }
      .editor-toolbar {
        display: grid;
        grid-template-columns: minmax(160px, 1fr) minmax(160px, 1fr) auto auto;
        gap: 16px;
        align-items: end;
        margin-block-end: 18px;
      }
      .switch-label {
        display: flex;
        align-items: center;
        gap: 8px;
        min-block-size: 44px;
      }
      .switch-label input {
        inline-size: 20px;
        min-block-size: 20px;
      }
      .profile-summary {
        display: grid;
        gap: 5px;
      }
      .profile-summary > span,
      .profile-summary small,
      label small {
        color: var(--secondary-text-color);
        font-size: 0.76rem;
        line-height: 1.35;
      }
      .template-tools,
      .mode-guidance,
      .copy-tool,
      .preview-card,
      .save-bar {
        border: 1px solid var(--ic-border);
        border-radius: 16px;
        background: var(--ic-surface);
        padding: 16px;
        margin-block: 16px;
      }
      .mode-guidance {
        display: grid;
        grid-template-columns: minmax(150px, auto) 1fr;
        gap: 8px 20px;
        border: 1px solid var(--ic-border);
        border-inline-start: 4px solid var(--info-color, #039be5);
        border-radius: 12px;
        background: var(--ic-surface);
        padding: 14px 16px;
      }
      .mode-guidance div {
        display: grid;
      }
      .mode-guidance span,
      .mode-guidance small {
        color: var(--secondary-text-color);
        font-size: 0.78rem;
      }
      .mode-guidance small {
        grid-column: 1 / -1;
      }
      .mode-warning {
        margin-block-start: 10px;
        border-inline-start: 3px solid var(--warning-color, #f9a825);
        padding-inline-start: 10px;
        font-size: 0.82rem;
      }
      .template-tools {
        display: grid;
        grid-template-columns: minmax(220px, 1fr) minmax(360px, 2fr) auto;
        align-items: end;
        gap: 16px;
      }
      .starter-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
      }
      .starter-grid fieldset {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        min-inline-size: 0;
        margin: 0;
        padding: 8px;
        border: 1px solid var(--ic-border);
        border-radius: 10px;
      }
      .starter-grid legend {
        padding-inline: 4px;
        font-size: 0.8rem;
        font-weight: 700;
      }
      .template-actions {
        display: grid;
        gap: 8px;
      }
      h3,
      p {
        margin-block: 0;
      }
      p {
        color: var(--secondary-text-color);
        line-height: 1.5;
      }
      .mobile-day-picker {
        display: none;
      }
      .week-grid {
        display: grid;
        grid-template-columns: repeat(7, minmax(215px, 1fr));
        gap: 12px;
        overflow-x: auto;
        padding-block: 4px 12px;
        scroll-snap-type: inline proximity;
      }
      .day-column {
        border: 1px solid var(--ic-border);
        border-radius: 14px;
        background: color-mix(in srgb, var(--ic-surface) 96%, var(--ic-accent));
        padding: 12px;
        scroll-snap-align: start;
      }
      .day-column > header {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        align-items: start;
      }
      .day-actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: end;
        gap: 4px;
      }
      .day-actions button {
        min-block-size: 36px;
        padding: 5px 7px;
        font-size: 0.72rem;
      }
      .clear-confirmation {
        margin-block-start: 10px;
        padding: 10px;
        border: 1px solid var(--warning-color, #f9a825);
        border-radius: 10px;
        background: color-mix(
          in srgb,
          var(--warning-color, #f9a825) 9%,
          transparent
        );
      }
      .clear-confirmation div {
        display: flex;
        justify-content: end;
        gap: 8px;
        margin-block-start: 8px;
      }
      .day-column header span {
        color: var(--secondary-text-color);
        font-size: 0.8rem;
      }
      .day-column ol {
        list-style: none;
        padding: 0;
        margin: 10px 0 0;
        display: grid;
        gap: 10px;
      }
      .inheritance {
        font-size: 0.78rem;
        padding: 8px;
        margin-block-start: 10px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--ic-accent) 8%, transparent);
      }
      .period {
        border: 1px solid var(--ic-border);
        border-radius: 12px;
        background: var(--primary-background-color);
        padding: 10px;
      }
      .period.current {
        border-color: var(--ic-accent);
        box-shadow: inset 3px 0 var(--ic-accent);
      }
      .period.invalid {
        border-color: var(--error-color, #c62828);
      }
      .period-heading {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 6px;
        margin-block-end: 10px;
      }
      .period-heading div {
        display: flex;
        gap: 4px;
      }
      .period-heading button {
        min-block-size: 36px;
        padding: 5px 7px;
        font-size: 0.72rem;
      }
      .field-grid {
        display: grid;
        gap: 9px;
      }
      .field-error {
        color: var(--error-color, #c62828);
        font-size: 0.78rem;
        margin-block-start: 8px;
      }
      .copy-tool {
        display: grid;
        grid-template-columns: minmax(180px, 1fr) minmax(150px, 0.6fr) 2fr auto;
        align-items: center;
        gap: 16px;
      }
      .copy-days {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 16px;
      }
      .copy-days label {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .copy-days input {
        inline-size: 18px;
        min-block-size: 18px;
      }
      .preview-card > div:first-child {
        display: flex;
        justify-content: space-between;
        gap: 12px;
      }
      .preview-card dl {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
      }
      .preview-card dl div {
        padding: 10px;
        border-radius: 10px;
        background: var(--primary-background-color);
      }
      .preview-card dt {
        color: var(--secondary-text-color);
        font-size: 0.78rem;
      }
      .preview-card dd {
        margin: 4px 0 0;
        font-weight: 700;
      }
      .dst-warnings {
        padding-inline-start: 20px;
      }
      .dst-warnings li {
        margin-block: 8px;
      }
      .dst-warnings span {
        display: block;
        color: var(--secondary-text-color);
      }
      .no-warning {
        margin-block: 12px;
      }
      .preview-boundary {
        font-size: 0.78rem;
      }
      .save-bar {
        position: sticky;
        inset-block-end: 12px;
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 10px;
        align-items: center;
        box-shadow: var(--ha-card-box-shadow, 0 8px 24px rgba(0, 0, 0, 0.12));
        z-index: 2;
      }
      .save-bar.dirty {
        border-color: var(--warning-color, #f9a825);
      }
      .save-bar div {
        display: grid;
      }
      .save-bar span {
        color: var(--secondary-text-color);
        font-size: 0.8rem;
      }
      .validation {
        border: 2px solid var(--error-color, #c62828);
        border-radius: 12px;
        padding: 14px;
        color: var(--error-color, #c62828);
      }
      .validation p {
        color: inherit;
      }
      @media (max-width: 900px) {
        .editor-toolbar {
          grid-template-columns: 1fr 1fr;
        }
        .template-tools {
          grid-template-columns: 1fr;
          align-items: stretch;
        }
        .starter-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .mobile-day-picker {
          display: grid;
          margin-block: 14px;
        }
        .week-grid {
          display: block;
          overflow: visible;
        }
        .day-column.mobile-hidden {
          display: none;
        }
        .copy-tool {
          grid-template-columns: 1fr;
        }
        .preview-card dl {
          grid-template-columns: 1fr 1fr;
        }
      }
      @media (max-width: 480px) {
        .editor-toolbar {
          grid-template-columns: 1fr;
        }
        .template-actions button {
          inline-size: 100%;
        }
        .starter-grid {
          grid-template-columns: 1fr;
        }
        .preview-card dl {
          grid-template-columns: 1fr;
        }
        .save-bar {
          grid-template-columns: 1fr 1fr;
        }
        .save-bar div {
          grid-column: 1 / -1;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        * {
          scroll-behavior: auto !important;
        }
      }
    `
];
let he = ae;
customElements.define("ic-schedule-editor", he);
const Wt = {
  effective_temperature: "Indoor temperature",
  effective_humidity: "Indoor humidity",
  outdoor_temperature: "Outdoor temperature",
  scheduled_target: "Scheduled target",
  scheduled_heat_target: "Scheduled heat target",
  scheduled_cool_target: "Scheduled cool target",
  effective_target: "Effective target",
  effective_heat_target: "Effective heat target",
  effective_cool_target: "Effective cool target",
  hvac_action: "HVAC operation",
  fan_action: "Fan-only circulation",
  contact_state: "Window / door",
  control_context: "Control context"
}, Qt = {
  off: "Off",
  idle: "Idle",
  heating: "Heating",
  cooling: "Cooling",
  drying: "Drying",
  fan: "Fan only",
  on: "On",
  not_reported: "Not reported",
  unavailable: "Unavailable",
  unknown: "Unknown (older sample)",
  open: "Open",
  closed: "Closed",
  normal: "Normal",
  window_suspended: "Paused for open window / door",
  manual_override: "Manual override",
  shared_conflict: "Shared-equipment conflict",
  safe_fallback: "Safe fallback",
  paused: "Paused",
  degraded: "Degraded"
}, X = 30, ee = 155, Jt = ee - X, Me = [30, 61.25, 92.5, 123.75, 155], Xt = 300 * 1e3, ei = 900 * 1e3;
function Ke(r) {
  return Wt[r] ?? r.replaceAll("_", " ");
}
function We(r) {
  return typeof r == "string" ? Qt[r] ?? Ke(r) : String(r);
}
function ti(r) {
  return r.filter(
    (e, t) => t === 0 || r[t - 1]?.value !== e.value
  );
}
function ii(r) {
  return typeof r.value == "string";
}
function ai(r) {
  switch (r) {
    case "heating":
      return "Running with heating";
    case "cooling":
      return "Running with cooling";
    case "drying":
      return "Running with drying";
    case "fan":
      return "Running fan only";
    case "off":
    case "idle":
      return "Not running";
    default:
      return We(r);
  }
}
function L(r) {
  return r.samples.filter(
    (e) => typeof e.value == "number"
  );
}
function ri(r, e) {
  if (r.length === 0)
    return "";
  const t = r[0];
  if (t === void 0)
    return "";
  let i = `M ${t.x.toFixed(2)} ${t.y.toFixed(2)}`;
  for (const a of r.slice(1))
    i += e ? ` H ${a.x.toFixed(2)} V ${a.y.toFixed(2)}` : ` L ${a.x.toFixed(2)} ${a.y.toFixed(2)}`;
  return i;
}
const re = class re extends I {
  constructor() {
    super(...arguments), this.locale = "en-US", this.temperatureUnit = "°C";
  }
  updated(e) {
    e.has("timeline") && this.setAttribute(
      "aria-label",
      this.timeline === void 0 ? "Today climate timeline unavailable" : `Today climate timeline for ${this.timeline.local_date}`
    );
  }
  render() {
    if (this.timeline === void 0)
      return c`<div class="empty" role="status">
        Today’s timeline is not available yet. Observation continues normally.
      </div>`;
    const e = this.timeline, t = this.temperatureRange(e), i = this.chartWindow(e), a = this.renderedSeries(e, t, i), n = a.find(
      (d) => d.kind === "effective_temperature"
    ), s = n?.sampleCount ?? 0, l = s >= 2, o = this.stateLanes(e, i), p = this.currentCursor(i), m = this.timeTicks(i, e);
    return c`
      <div class="legend" aria-label="Timeline legend">
        ${a.map(
      (d) => c`<span class="legend-item">
              <span
                class="swatch ${d.className}"
                aria-hidden="true"
              ></span>
              ${d.label}
              <small>${d.valueKind}</small>
            </span>`
    )}
      </div>
      ${a.length === 0 ? c`<div class="empty" role="status">
              No numeric observations yet.
            </div>` : l ? c`<div class="chart-wrap">
                <svg
                  viewBox="0 0 1000 210"
                  role="img"
                  aria-labelledby="timeline-title timeline-description"
                >
                  <title id="timeline-title">
                    Today climate observations and targets
                  </title>
                  <desc id="timeline-description">
                    Solid lines are measured. Dashed lines are configured.
                    Dotted lines are calculated. Exact values follow in the
                    accessible table.
                  </desc>
                  <g class="grid" aria-hidden="true">
                    ${Me.map(
      (d) => A`<line x1="80" x2="970" y1=${d} y2=${d}></line>`
    )}
                    ${m.map(
      (d) => A`<line
                          x1=${d.x}
                          x2=${d.x}
                          y1=${X}
                          y2=${ee}
                        ></line>`
    )}
                  </g>
                  <g class="y-axis-labels" aria-hidden="true">
                    ${Me.map((d, h) => {
      const [f, y] = t, C = y - (y - f) * h / 4;
      return A`<text x="72" y=${d + 6} text-anchor="end">
                        ${ie(
        C,
        this.temperatureUnit,
        this.locale
      )}
                      </text>`;
    })}
                  </g>
                  ${a.map(
      (d) => A`<g class="series-group ${d.className}">
                        <path
                          class="series ${d.className}"
                          d=${d.path}
                        ></path>
                        ${d.kind === "effective_temperature" && d.sampleCount <= 3 ? d.points.map(
        (h) => A`<circle
                                    class="sample-point measured-temperature"
                                    cx=${h.x}
                                    cy=${h.y}
                                    r="4.5"
                                  ></circle>`
      ) : g}
                      </g>`
    )}
                  ${p === null ? g : A`<line
                          class="now"
                          x1=${p}
                          x2=${p}
                          y1=${X - 5}
                          y2=${ee + 5}
                        ></line>`}
                  ${e.annotations.map((d) => {
      const h = this.xPosition(
        Date.parse(d.timestamp_utc),
        i
      );
      return A`<g class="annotation" aria-hidden="true">
                      <circle cx=${h} cy="15" r="6"></circle>
                      <line x1=${h} x2=${h} y1="21" y2=${X + 6}></line>
                    </g>`;
    })}
                  <g class="axis-labels" aria-hidden="true">
                    ${m.map(
      (d) => A`<text
                          x=${d.x}
                          y="198"
                          text-anchor=${d.anchor}
                        >${d.label}</text>`
    )}
                  </g>
                </svg>
                ${this.sampleSummary(n)}
              </div>` : c`<div class="empty collecting" role="status">
                <div>
                  <strong>Collecting climate history</strong>
                  <p>
                    ${s} of 2 temperature samples collected. The
                    chart will appear after the next observation.
                  </p>
                  ${this.sampleSummary(n)}
                </div>
              </div>`}
      ${o.length === 0 ? g : c`<div
              class="state-lanes-scroll"
              aria-label="Equipment and context state timeline"
            >
              <div class="state-lanes">
                ${o.map((d) => this.renderStateLane(d))}
              </div>
            </div>`}
      <p class="capability">${e.capability_statement}</p>
      <details>
        <summary>Accessible timeline data</summary>
        <div class="table-scroll">
          <table>
            <caption>
              Latest factual value and coverage for each available series
            </caption>
            <thead>
              <tr>
                <th scope="col">Series</th>
                <th scope="col">Provenance</th>
                <th scope="col">Latest</th>
                <th scope="col">Coverage</th>
                <th scope="col">Gaps</th>
              </tr>
            </thead>
            <tbody>
              ${a.map(
      (d) => c`<tr>
                    <th scope="row">${d.label}</th>
                    <td>${d.valueKind}</td>
                    <td>${this.latestValue(d)}</td>
                    <td>${d.coverage}</td>
                    <td>${d.gaps}</td>
                  </tr>`
    )}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }
  renderedSeries(e, t, i) {
    return this.visibleNumericSeries(e).filter(
      (n) => L(n).length > 0 && n.unit !== "%"
    ).map((n) => {
      const s = L(n), l = s.map((p) => ({
        x: this.xPosition(Date.parse(p.timestamp_utc), i),
        y: this.yPosition(p.value, t)
      })), o = s.at(-1);
      if (o === void 0)
        throw new Error("validated timeline series unexpectedly empty");
      return {
        kind: n.kind,
        valueKind: n.value_kind,
        label: Ke(n.kind),
        className: `${n.value_kind} ${n.kind}`,
        path: ri(l, n.value_kind !== "measured"),
        points: l,
        latest: o.value,
        latestTimestamp: o.timestamp_utc,
        sampleCount: s.length,
        coverage: `${G(
          n.coverage_start_utc,
          this.locale,
          e.time_zone
        )} – ${G(
          n.coverage_end_utc,
          this.locale,
          e.time_zone
        )}`,
        gaps: n.missing_intervals.length
      };
    });
  }
  visibleNumericSeries(e) {
    const t = {
      effective_target: "scheduled_target",
      effective_heat_target: "scheduled_heat_target",
      effective_cool_target: "scheduled_cool_target"
    };
    return e.series.filter((i) => {
      const a = t[i.kind];
      if (a === void 0) return !0;
      const n = e.series.find(
        (s) => s.kind === a
      );
      return n === void 0 || !this.sameNumericSeries(i, n);
    });
  }
  sameNumericSeries(e, t) {
    const i = L(e), a = L(t);
    return i.length === a.length && i.every((n, s) => {
      const l = a[s];
      return n.timestamp_utc === l?.timestamp_utc && n.value === l.value;
    });
  }
  temperatureRange(e) {
    return this.range(
      e.series.filter((t) => t.unit === "°C").flatMap(
        (t) => L(t).map((i) => i.value)
      )
    );
  }
  sampleSummary(e) {
    return e === void 0 ? g : c`<p class="sample-summary">
      Latest sample
      ${G(
      e.latestTimestamp,
      this.locale,
      this.timeline?.time_zone
    )}
      · Source: effective zone temperature
    </p>`;
  }
  stateLanes(e, t) {
    const i = e.series.find(
      (o) => o.kind === "hvac_action"
    ), a = e.series.find((o) => o.kind === "fan_action"), n = e.series.find(
      (o) => o.kind === "contact_state"
    ), s = e.series.find(
      (o) => o.kind === "control_context"
    ), l = [];
    return i !== void 0 && l.push(
      this.buildStateLane(
        i,
        t,
        "Heating",
        "Actual thermostat heating operation",
        "heating",
        (o) => o === "heating"
      ),
      this.buildStateLane(
        i,
        t,
        "Cooling",
        "Actual thermostat cooling operation",
        "cooling",
        (o) => o === "cooling"
      ),
      this.buildStateLane(
        i,
        t,
        "Air handler",
        "Derived from actual thermostat operation",
        "air-handler derived",
        (o) => ["heating", "cooling", "drying", "fan"].includes(o),
        ai
      )
    ), a !== void 0 && l.splice(
      Math.min(2, l.length),
      0,
      this.buildStateLane(
        a,
        t,
        "Fan only",
        "Explicit circulation without heating or cooling",
        "fan-only",
        (o) => o === "on"
      )
    ), n?.samples.some((o) => o.value !== "not_configured") === !0 && l.push(
      this.buildStateLane(
        n,
        t,
        "Window / door",
        "Any configured contact open or unavailable",
        "contact",
        (o) => o === "open" || o === "unavailable"
      )
    ), s?.samples.some(
      (o) => o.value !== "normal" && o.value !== "not_reported"
    ) === !0 && l.push(
      this.buildStateLane(
        s,
        t,
        "Control context",
        "Recorded override, suspension, fallback, or pause",
        "context",
        (o) => o !== "normal" && o !== "not_reported"
      )
    ), l;
  }
  buildStateLane(e, t, i, a, n, s, l = We) {
    const o = ti(e.samples).filter(ii), p = Math.min(
      t.end,
      Date.parse(e.coverage_end_utc)
    ), m = o.flatMap((d, h) => {
      if (!s(d.value)) return [];
      const f = Math.max(
        t.start,
        Date.parse(d.timestamp_utc)
      ), y = o[h + 1], C = Math.min(
        p,
        y === void 0 ? p : Date.parse(y.timestamp_utc)
      );
      if (C <= f) return [];
      const ce = t.end - t.start;
      return [
        {
          left: (f - t.start) / ce * 100,
          width: (C - f) / ce * 100,
          value: d.value,
          label: l(d.value),
          className: `${n} ${d.value}`,
          startsAt: this.stateTimestamp(new Date(f).toISOString()),
          endsAt: this.stateTimestamp(new Date(C).toISOString())
        }
      ];
    });
    return { label: i, detail: a, className: n, segments: m };
  }
  renderStateLane(e) {
    return c`<div class="lane-row ${e.className}">
      <span class="lane-label">
        <strong>${e.label}</strong>
        <small>${e.detail}</small>
      </span>
      <div class="lane-track">
        ${e.segments.map(
      (t) => c`<span
              class="lane-segment ${t.className}"
              style=${`inset-inline-start:${String(t.left)}%;inline-size:${String(t.width)}%`}
              tabindex="0"
              aria-label=${`${e.label}: ${t.label}, ${t.startsAt} to ${t.endsAt}`}
              title=${`${t.label} · ${t.startsAt}–${t.endsAt}`}
            ></span>`
    )}
      </div>
      <span aria-hidden="true"></span>
    </div>`;
  }
  stateTimestamp(e) {
    return G(e, this.locale, this.timeline?.time_zone);
  }
  range(e) {
    if (e.length === 0)
      return [0, 1];
    const t = Math.min(...e), i = Math.max(...e), a = Math.max((i - t) * 0.15, 0.5);
    return [t - a, i + a];
  }
  xPosition(e, t) {
    return 80 + (e - t.start) / (t.end - t.start) * 890;
  }
  yPosition(e, t) {
    const [i, a] = t;
    return ee - (e - i) / (a - i) * Jt;
  }
  currentCursor(e) {
    const t = Date.now();
    return t < e.start || t > e.end ? null : this.xPosition(t, e);
  }
  chartWindow(e) {
    const t = Date.parse(e.day_start_utc), i = Date.parse(e.day_end_utc), a = e.series.filter((f) => f.unit !== "%").flatMap(
      (f) => L(f).map(
        (y) => Date.parse(y.timestamp_utc)
      )
    ).filter((f) => Number.isFinite(f));
    if (a.length === 0)
      return { start: t, end: i };
    const n = Math.min(...a), s = Math.max(...a), l = i - t, o = Math.max(
      ei,
      s - n + Xt * 2
    ), p = Math.min(l, o), m = (n + s) / 2;
    let d = m - p / 2, h = m + p / 2;
    return d < t && (d = t, h = t + p), h > i && (h = i, d = i - p), { start: d, end: h };
  }
  timeTicks(e, t) {
    const i = e.end - e.start, a = i <= 30 * 6e4 ? 5 : i <= 90 * 6e4 ? 15 : i <= 180 * 6e4 ? 30 : i <= 480 * 6e4 ? 60 : 120, n = new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      hourCycle: "h23",
      minute: "2-digit",
      timeZone: t.time_zone
    }), s = new Intl.DateTimeFormat(this.locale, {
      hour: "numeric",
      timeZone: t.time_zone
    }), l = new Intl.DateTimeFormat(this.locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: t.time_zone
    }), o = Date.parse(t.day_start_utc), p = Date.parse(t.day_end_utc), m = Math.min(a, 15) * 6e4, d = [];
    for (let h = o; h < p && h < e.end; h += m) {
      if (h < e.start) continue;
      const f = Object.fromEntries(
        n.formatToParts(new Date(h)).filter((Z) => Z.type === "hour" || Z.type === "minute").map((Z) => [Z.type, Number(Z.value)])
      ), y = f.hour, C = f.minute;
      if (y === void 0 || C === void 0) continue;
      (y * 60 + C) % a === 0 && d.push(h);
    }
    return d.map((h, f) => ({
      timestamp: h,
      x: this.xPosition(h, e),
      label: a < 60 ? l.format(new Date(h)) : s.format(new Date(h)),
      anchor: f === 0 && h === e.start ? "start" : f === d.length - 1 && h === e.end ? "end" : "middle"
    }));
  }
  latestValue(e) {
    return typeof e.latest != "number" ? e.latest : ie(e.latest, this.temperatureUnit, this.locale);
  }
};
re.properties = {
  timeline: { attribute: !1 },
  locale: { type: String },
  temperatureUnit: { type: String, attribute: "temperature-unit" }
}, re.styles = se`
    :host {
      display: block;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      margin-block: 4px 16px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 0.84rem;
    }
    .legend-item small {
      color: var(--secondary-text-color);
      text-transform: capitalize;
    }
    .swatch {
      inline-size: 28px;
      border-block-start: 3px solid var(--ic-accent);
    }
    .swatch.configured {
      border-block-start-style: dashed;
    }
    .swatch.calculated {
      border-block-start-style: dotted;
    }
    .swatch.scheduled_heat_target,
    .swatch.effective_heat_target {
      border-block-start-color: var(--warning-color, #d97706);
    }
    .swatch.scheduled_cool_target,
    .swatch.effective_cool_target {
      border-block-start-color: var(--info-color, #1976d2);
    }
    .chart-wrap {
      overflow: hidden;
      min-block-size: 150px;
    }
    svg {
      display: block;
      inline-size: 100%;
      min-inline-size: 620px;
      block-size: auto;
    }
    .grid line {
      stroke: var(--divider-color, #d8dde3);
      stroke-width: 1;
    }
    .series {
      fill: none;
      stroke: var(--ic-accent, var(--primary-color, #03a9f4));
      stroke-width: 4;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .sample-point {
      fill: var(--ic-surface, var(--card-background-color, #ffffff));
      stroke: var(--ic-accent, var(--primary-color, #03a9f4));
      stroke-width: 3;
    }
    .series.configured {
      stroke-dasharray: 14 8;
      stroke: var(--warning-color, #d97706);
    }
    .series.scheduled_heat_target {
      stroke: var(--warning-color, #d97706);
    }
    .series.scheduled_cool_target {
      stroke: var(--info-color, #1976d2);
    }
    .series.effective_heat_target {
      stroke: var(--warning-color, #d97706);
    }
    .series.effective_cool_target {
      stroke: var(--info-color, #1976d2);
    }
    .series.calculated {
      stroke-dasharray: 3 7;
      stroke: var(--success-color, #1f9d68);
    }
    .series.outdoor_temperature {
      stroke: var(--secondary-text-color, #667085);
      stroke-dasharray: 18 7;
      stroke-width: 2;
    }
    .now {
      stroke: var(--error-color, #d93025);
      stroke-width: 2;
    }
    .annotation circle,
    .annotation line {
      fill: var(--warning-color, #d97706);
      stroke: var(--warning-color, #d97706);
    }
    .axis-labels {
      fill: var(--secondary-text-color, #667085);
      font-size: 16px;
    }
    .y-axis-labels {
      fill: var(--secondary-text-color, #667085);
      font-size: 16px;
    }
    .state-lanes-scroll {
      overflow-x: auto;
      margin-block: 12px;
    }
    .state-lanes {
      display: grid;
      gap: 6px;
      min-inline-size: 620px;
    }
    .lane-row {
      display: grid;
      grid-template-columns: 80fr 890fr 30fr;
      align-items: center;
      min-block-size: 30px;
    }
    .lane-label {
      display: grid;
      padding-inline-end: 8px;
      font-size: 0.72rem;
      line-height: 1.15;
    }
    .lane-label small {
      display: block;
      color: var(--secondary-text-color, #667085);
      font-size: 0.58rem;
      font-weight: 500;
    }
    .lane-track {
      position: relative;
      block-size: 15px;
      border: 1px solid var(--divider-color, #d8dde3);
      border-radius: 5px;
      background: color-mix(
        in srgb,
        var(--secondary-text-color, #667085) 7%,
        transparent
      );
      overflow: hidden;
    }
    .lane-segment {
      position: absolute;
      inset-block: 0;
      min-inline-size: 2px;
      background: var(--ic-accent, #0288d1);
    }
    .lane-segment:focus-visible {
      outline: 3px solid var(--primary-text-color);
      outline-offset: -3px;
    }
    .lane-segment.heating {
      background: var(--warning-color, #ef6c00);
    }
    .lane-segment.cooling {
      background: var(--info-color, #1976d2);
    }
    .lane-segment.fan-only,
    .lane-segment.fan {
      background: var(--success-color, #2e7d32);
    }
    .lane-segment.air-handler {
      background: repeating-linear-gradient(
        135deg,
        var(--secondary-text-color, #667085),
        var(--secondary-text-color, #667085) 4px,
        transparent 4px,
        transparent 8px
      );
    }
    .lane-segment.contact.open {
      background: var(--warning-color, #ef6c00);
    }
    .lane-segment.contact.unavailable,
    .lane-segment.context.degraded,
    .lane-segment.context.safe_fallback {
      background: repeating-linear-gradient(
        135deg,
        var(--error-color, #c62828),
        var(--error-color, #c62828) 4px,
        transparent 4px,
        transparent 8px
      );
    }
    .lane-segment.context {
      background: var(--warning-color, #ef6c00);
    }
    .capability,
    .empty,
    .sample-summary {
      color: var(--secondary-text-color, #667085);
      font-size: 0.9rem;
    }
    .sample-summary {
      margin: 8px 0 0;
    }
    .empty {
      min-block-size: 180px;
      display: grid;
      place-items: center;
      border: 1px dashed var(--divider-color, #d8dde3);
      border-radius: 14px;
      text-align: center;
      padding: 24px;
    }
    .empty.collecting {
      min-block-size: 96px;
    }
    .empty.collecting p {
      margin: 6px 0 0;
    }
    summary {
      min-block-size: 44px;
      display: flex;
      align-items: center;
      cursor: pointer;
      font-weight: 600;
    }
    .table-scroll {
      overflow-x: auto;
    }
    table {
      inline-size: 100%;
      border-collapse: collapse;
      font-size: 0.84rem;
    }
    caption {
      text-align: start;
      color: var(--secondary-text-color, #667085);
      margin-block-end: 8px;
    }
    th,
    td {
      padding: 10px;
      border-block-end: 1px solid var(--divider-color, #d8dde3);
      text-align: start;
      white-space: nowrap;
    }
    @media (max-width: 700px) {
      .chart-wrap {
        overflow-x: auto;
      }
    }
  `;
let ge = re;
customElements.get("ic-today-timeline") || customElements.define("ic-today-timeline", ge);
const me = "intelligent-climate.temperature-unit";
function ni() {
  try {
    const r = window.localStorage.getItem(me);
    if (r === "fahrenheit" || r === "celsius")
      return r;
  } catch {
  }
  return "home_assistant";
}
function si(r) {
  try {
    r === "home_assistant" ? window.localStorage.removeItem(me) : window.localStorage.setItem(me, r);
  } catch {
  }
}
function oi(r, e) {
  return r === "fahrenheit" ? "°F" : r === "celsius" ? "°C" : e;
}
const li = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
];
function ci(r, e, t = /* @__PURE__ */ new Date()) {
  const i = ui(
    e.config.equipment_group,
    "config.equipment_group"
  ), a = Oe(
    i.equipment_group_id,
    "config.equipment_group.equipment_group_id"
  ), n = Oe(
    e.config.acknowledged_time_zone,
    "config.acknowledged_time_zone"
  ), s = {};
  for (const l of e.zones) {
    const o = Ye();
    s[l.zone_id] = {
      zone_id: l.zone_id,
      enabled: !1,
      selected_profile_id: o,
      profiles: [di(o)]
    };
  }
  return {
    schedule_schema_version: 1,
    entry_id: r,
    equipment_group_id: a,
    time_zone: n,
    revision: 0,
    zones: s,
    saved_at_utc: t.toISOString()
  };
}
function Ue(r, e = /* @__PURE__ */ new Date()) {
  return { ...structuredClone(r), saved_at_utc: e.toISOString() };
}
function di(r) {
  const e = {};
  for (const t of li)
    e[t] = [];
  return {
    profile_id: r,
    name: "Normal",
    enabled: !0,
    days: e
  };
}
function ui(r, e) {
  if (typeof r != "object" || r === null || Array.isArray(r))
    throw new Error(`${e} is unavailable`);
  return r;
}
function Oe(r, e) {
  if (typeof r != "string" || r.length === 0)
    throw new Error(`${e} is unavailable`);
  return r;
}
const Qe = [
  { id: "overview", label: "Overview", icon: "⌂" },
  { id: "schedule", label: "Schedule", icon: "▦" },
  { id: "sensors", label: "Sensors", icon: "◫" },
  { id: "activity", label: "Activity", icon: "↯" },
  { id: "settings", label: "Settings", icon: "⚙" }
];
function pi(r) {
  return Qe.some((e) => e.id === r);
}
const ne = class ne extends I {
  constructor() {
    super(...arguments), this.narrow = !1, this.activeRoute = "overview", this.selectedEntryId = "", this.selectedZoneId = "", this.loading = !0, this.errorMessage = "", this.activityFilter = "all", this.temperatureUnitPreference = ni(), this.activityLoadingOlder = !1, this.scheduleLoading = !1, this.scheduleSaving = !1, this.scheduleDirty = !1, this.scheduleMessage = "", this.scheduleConflict = !1, this.loadGeneration = 0, this.detailLoadGeneration = 0, this.entryChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLSelectElement && this.confirmDiscard("overview") && (this.selectedEntryId = t.value, this.loadEntry(t.value));
    }, this.filterChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLSelectElement && (this.activityFilter = t.value);
    }, this.temperatureUnitChanged = (e) => {
      const t = e.currentTarget;
      if (!(t instanceof HTMLSelectElement))
        return;
      const i = t.value;
      i !== "home_assistant" && i !== "fahrenheit" && i !== "celsius" || (this.temperatureUnitPreference = i, si(i));
    }, this.loadOlderActivity = async () => {
      if (this.client === void 0 || this.data === void 0 || this.activityLoadingOlder)
        return;
      const e = this.data, t = this.loadGeneration;
      this.activityLoadingOlder = !0;
      try {
        const i = await this.client.activity(
          e.activity.records.length,
          100,
          "newest"
        );
        if (t !== this.loadGeneration)
          return;
        const a = new Set(
          e.activity.records.map((s) => s.record_id)
        ), n = [
          ...e.activity.records,
          ...i.records.filter((s) => !a.has(s.record_id))
        ];
        this.data = {
          ...e,
          activity: { ...i, offset: 0, records: n }
        };
      } catch (i) {
        this.errorMessage = this.describeError(i);
      } finally {
        this.activityLoadingOlder = !1;
      }
    }, this.refreshDetails = () => {
      this.loadZoneDetails(this.loadGeneration);
    }, this.retry = () => {
      this.selectedEntryId.length > 0 ? this.loadEntry(this.selectedEntryId) : this.initialize();
    }, this.scheduleChanged = (e) => {
      this.scheduleDocument = e.detail.document, this.scheduleDirty = !0, this.schedulePreview = void 0, this.scheduleMessage = "", this.scheduleConflict = !1;
    }, this.previewSchedule = async () => {
      if (!(this.client === void 0 || this.scheduleDocument === void 0)) {
        this.scheduleMessage = "";
        try {
          const e = Ue(this.scheduleDocument);
          await this.client.validateSchedule(e), this.schedulePreview = await this.client.previewSchedule(e);
        } catch (e) {
          this.schedulePreview = void 0, this.scheduleMessage = this.describeScheduleError(e);
        }
      }
    }, this.saveSchedule = async () => {
      if (!(this.client === void 0 || this.scheduleDocument === void 0 || this.scheduleSaving)) {
        this.scheduleSaving = !0, this.scheduleMessage = "", this.scheduleConflict = !1;
        try {
          const e = this.scheduleDocument.revision, t = Ue(this.scheduleDocument);
          await this.client.validateSchedule(t);
          const i = await this.client.saveSchedule(t, e);
          this.scheduleDocument = i.schedule, this.scheduleDirty = !1, this.schedulePreview = await this.client.previewSchedule(i.schedule);
        } catch (e) {
          const t = this.errorCode(e);
          this.scheduleConflict = t === "revision_conflict", this.scheduleMessage = this.describeScheduleError(e);
        } finally {
          this.scheduleSaving = !1;
        }
      }
    }, this.reloadSchedule = () => {
      this.scheduleDirty && !window.confirm("Discard this unsaved schedule draft and reload?") || this.loadSchedule(this.loadGeneration);
    }, this.beforeUnload = (e) => {
      this.scheduleDirty && e.preventDefault();
    };
  }
  connectedCallback() {
    super.connectedCallback(), window.addEventListener("beforeunload", this.beforeUnload);
  }
  disconnectedCallback() {
    this.loadGeneration += 1, this.detailLoadGeneration += 1, this.unsubscribe?.(), this.unsubscribe = void 0, window.removeEventListener("beforeunload", this.beforeUnload), super.disconnectedCallback();
  }
  willUpdate(e) {
    if (e.has("route")) {
      const t = this.route?.path?.split("/").find(Boolean);
      t !== void 0 && pi(t) && (this.activeRoute = t);
    }
  }
  updated(e) {
    (e.has("hass") || e.has("panel")) && this.client === void 0 && this.initialize();
  }
  render() {
    const e = this.entries();
    return c`
      <div class="app-shell">
        <header class="topbar">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">IC</span>
            <div>
              <h1>Intelligent Climate</h1>
              <p>See what your home is doing—and why.</p>
            </div>
          </div>
          ${e.length > 1 ? c`<label class="entry-picker">
                  <span>Equipment group</span>
                  <select
                    .value=${this.selectedEntryId}
                    @change=${this.entryChanged}
                  >
                    ${e.map(
      (t) => c`<option value=${t.entry_id}>
                          ${t.title}
                        </option>`
    )}
                  </select>
                </label>` : c`<div class="entry-name">
                  ${e[0]?.title ?? "Climate"}
                </div>`}
        </header>

        <nav class="primary-nav" aria-label="Intelligent Climate sections">
          ${Qe.map(
      (t) => c`<button
                type="button"
                class=${this.activeRoute === t.id ? "active" : ""}
                aria-current=${this.activeRoute === t.id ? "page" : g}
                @click=${() => this.navigate(t.id)}
              >
                <span aria-hidden="true">${t.icon}</span>
                ${t.label}
              </button>`
    )}
        </nav>

        <main id="main-content" tabindex="-1">
          ${this.loading ? this.renderLoading() : this.errorMessage.length > 0 ? this.renderError() : this.renderRoute()}
        </main>
      </div>
    `;
  }
  renderLoading() {
    return c`<div class="loading" role="status" aria-live="polite">
      <div class="spinner" aria-hidden="true"></div>
      <strong>Loading your climate picture…</strong>
      <span>Connecting to the local Intelligent Climate data.</span>
    </div>`;
  }
  renderError() {
    return c`<section class="error-card" role="alert">
      <span class="error-icon" aria-hidden="true">!</span>
      <div>
        <h2>We couldn’t load Intelligent Climate</h2>
        <p>${this.errorMessage}</p>
        <button type="button" class="primary-button" @click=${this.retry}>
          Try again
        </button>
      </div>
    </section>`;
  }
  renderRoute() {
    switch (this.activeRoute) {
      case "overview":
        return this.renderOverview();
      case "schedule":
        return this.renderSchedule();
      case "sensors":
        return this.renderSensors();
      case "activity":
        return this.renderActivity();
      case "settings":
        return this.renderSettings();
    }
  }
  renderSchedule() {
    const e = this.requireData();
    return c`
      <section class="page-heading with-action">
        <div>
          <span class="eyebrow">Local weekly comfort schedule</span>
          <h2>Schedule</h2>
          <p>
            Build an accessible weekly schedule with authoritative backend
            validation. Advanced drag editing and date exceptions remain a
            later-phase feature.
          </p>
        </div>
        <span class="schedule-safety">Read-only control preview</span>
      </section>
      ${this.scheduleLoading ? c`<div class="loading" role="status">Loading schedule…</div>` : this.scheduleDocument === void 0 ? c`<section class="error-card" role="alert">
                <div>
                  <h3>Schedule is unavailable</h3>
                  <p>${this.scheduleMessage}</p>
                  <button type="button" @click=${this.reloadSchedule}>
                    Try again
                  </button>
                </div>
              </section>` : c`${this.scheduleConflict ? c`<section class="schedule-conflict" role="alert">
                        <div>
                          <strong>A newer schedule revision exists.</strong>
                          <p>
                            Your draft was not overwritten. Reload the current
                            schedule before applying these edits again.
                          </p>
                        </div>
                        <button type="button" @click=${this.reloadSchedule}>
                          Reload current schedule
                        </button>
                      </section>` : g}
                <ic-schedule-editor
                  .document=${this.scheduleDocument}
                  .zones=${e.configuration.zones}
                  .zoneSnapshots=${e.snapshot.zones}
                  .preview=${this.schedulePreview}
                  .validationMessage=${this.scheduleMessage}
                  .saving=${this.scheduleSaving}
                  .dirty=${this.scheduleDirty}
                  .temperatureUnit=${this.temperatureUnit()}
                  .locale=${this.locale()}
                  @schedule-change=${this.scheduleChanged}
                  @schedule-preview=${this.previewSchedule}
                  @schedule-save=${this.saveSchedule}
                ></ic-schedule-editor>`}
    `;
  }
  renderOverview() {
    const e = this.requireData(), t = yt(e.snapshot.control_state), i = e.shadow.readiness, a = [
      "shadow_qualifying",
      "shadow_ready"
    ].includes(e.snapshot.control_state), n = this.selectedZone();
    return c`
      <section
        class="status-hero tone-${t.tone}"
        aria-labelledby="status-title"
      >
        <div class="status-copy">
          <span class="eyebrow">Current operating status</span>
          <h2 id="status-title">
            <span aria-hidden="true">${t.icon}</span> ${t.label}
          </h2>
          <p>
            ${t.automationOff ? "Automation is off. Sensors, thermostat state, weather context, activity, and history remain available." : "The safety path is evaluating current conditions. This read-only preview does not control your equipment."}
          </p>
          <div class="status-meta">
            <span>Revision ${e.snapshot.observation_revision}</span>
            <span>Updated ${this.time(e.snapshot.calculated_at_utc)}</span>
            <span
              >${e.snapshot.reason_code === null ? "No current alert" : U(e.snapshot.reason_code)}</span
            >
          </div>
        </div>
        <div class="hero-orbit" aria-hidden="true">
          <div class="orbit-ring"></div>
          <div class="orbit-value">${e.snapshot.zones.length}</div>
          <div class="orbit-label">
            ${e.snapshot.zones.length === 1 ? "zone" : "zones"}
          </div>
        </div>
      </section>

      <section class="metric-grid" aria-label="Climate summary">
        <article class="metric-card">
          <span class="metric-icon temp" aria-hidden="true">◒</span>
          <div>
            <span>Selected zone</span
            ><strong>${n?.name ?? "Unavailable"}</strong>
          </div>
          <b
            >${this.temperature(this.selectedZoneSnapshot()?.effective_temperature_c ?? null)}</b
          >
        </article>
        <article class="metric-card">
          <span class="metric-icon humidity" aria-hidden="true">◇</span>
          <div>
            <span>Humidity</span
            ><strong
              >${this.selectedZone()?.humidity_sources.some((s) => s.enabled) === !0 ? "Measured" : "Not configured"}</strong
            >
          </div>
          <b
            >${this.humidity(this.selectedZoneSnapshot()?.effective_humidity_pct ?? null, this.selectedZone()?.humidity_sources.some((s) => s.enabled) === !0)}</b
          >
        </article>
        <article class="metric-card">
          <span class="metric-icon source" aria-hidden="true">✓</span>
          <div>
            <span>Usable sources</span
            ><strong
              >${e.observation.degraded_zone_count === 0 ? "Healthy" : "Attention"}</strong
            >
          </div>
          <b>${e.observation.usable_temperature_sources}</b>
        </article>
        <article class="metric-card">
          <span class="metric-icon history" aria-hidden="true">↺</span>
          <div>
            <span>Local timeline</span><strong>Recent climate history</strong>
          </div>
          <b>${e.observation.presentation_history_hours}h</b>
        </article>
      </section>

      ${this.renderZoneSelector(e.configuration.zones)}

      <div class="overview-grid">
        <section class="card narrative-card" aria-labelledby="now-heading">
          <div class="card-heading">
            <div>
              <span class="eyebrow">Right now</span>
              <h2 id="now-heading">What Intelligent Climate sees</h2>
            </div>
            <button
              type="button"
              class="icon-button"
              aria-label="Refresh climate details"
              @click=${this.refreshDetails}
            >
              ↻
            </button>
          </div>
          ${this.narrative === void 0 ? c`<p class="muted">
                  A current explanation is not available yet.
                </p>` : c`<p class="narrative">${this.renderNarrative()}</p>`}
        </section>

        <section
          class="card readiness-card"
          aria-labelledby="readiness-heading"
        >
          <div class="card-heading">
            <div>
              <span class="eyebrow">Safe Scheduled Control</span>
              <h2 id="readiness-heading">Shadow readiness</h2>
            </div>
            <span
              class="readiness-state ${i?.ready === !0 ? "ready" : "waiting"}"
            >
              ${i?.ready === !0 ? "✓ Ready" : a ? "◌ Qualifying" : "○ Not started"}
            </span>
          </div>
          ${a ? i === null ? c`<p class="muted">
                    Scheduled Shadow is starting. Qualification evidence will
                    appear after its first valid evaluation.
                  </p>` : c`<div class="progress-row">
                      <div class="progress-label">
                        <span>Qualification</span
                        ><strong
                          >${Math.round(i.qualification_percent)}%</strong
                        >
                      </div>
                      <div
                        class="progress"
                        role="progressbar"
                        aria-label="Shadow qualification"
                        aria-valuemin="0"
                        aria-valuemax="100"
                        aria-valuenow=${i.qualification_percent}
                      >
                        <span
                          style=${`width: ${String(Math.min(100, Math.max(0, i.qualification_percent)))}%`}
                        ></span>
                      </div>
                    </div>
                    <dl class="readiness-facts">
                      <div>
                        <dt>Elapsed</dt>
                        <dd>${i.elapsed_hours.toFixed(1)} / 24 h</dd>
                      </div>
                      <div>
                        <dt>Decisions</dt>
                        <dd>${i.evaluated_decisions} / 20</dd>
                      </div>
                      <div>
                        <dt>Valid</dt>
                        <dd>
                          ${i.valid_evaluation_percent.toFixed(0)}%
                        </dd>
                      </div>
                      <div>
                        <dt>Transitions</dt>
                        <dd>${i.minimum_material_transitions} / 2</dd>
                      </div>
                    </dl>
                    ${i.blocking_reasons.length === 0 ? g : c`<p class="blocking">
                            <strong>Still needed:</strong>
                            ${i.blocking_reasons.map((s) => s.replaceAll("_", " ")).join(", ")}
                          </p>`}
                    ${i.blocking_faults.length === 0 ? g : c`<p class="fault">
                            <strong>Blocking fault:</strong>
                            ${i.blocking_faults.join(", ")}
                          </p>`}` : c`<p class="muted">
                  <strong>Not started — Scheduled Shadow is not active.</strong>
                  Ordinary observation history is still being collected.
                </p>`}
        </section>
      </div>

      <section class="card timeline-card" aria-labelledby="timeline-heading">
        <div class="card-heading">
          <div>
            <span class="eyebrow">Local day</span>
            <h2 id="timeline-heading">Today</h2>
          </div>
          <span class="provenance-note"
            >Measured · Configured · Calculated</span
          >
        </div>
        <ic-today-timeline
          .timeline=${this.timeline}
          .locale=${this.locale()}
          .temperatureUnit=${this.temperatureUnit()}
        ></ic-today-timeline>
      </section>

      <section class="card activity-preview" aria-labelledby="recent-heading">
        <div class="card-heading">
          <div>
            <span class="eyebrow">Only meaningful changes are recorded</span>
            <h2 id="recent-heading">Recent activity</h2>
          </div>
          <button
            type="button"
            class="text-button"
            @click=${() => this.navigate("activity")}
          >
            View all activity →
          </button>
        </div>
        ${this.renderActivityRecords(e.activity.records.slice(0, 5))}
      </section>
    `;
  }
  renderZoneSelector(e) {
    return e.length < 2 ? g : c`<div
      class="zone-tabs"
      role="tablist"
      aria-label="Climate zones"
    >
      ${e.map(
      (t) => c`<button
            type="button"
            role="tab"
            aria-selected=${this.selectedZoneId === t.zone_id}
            class=${this.selectedZoneId === t.zone_id ? "active" : ""}
            @click=${() => this.selectZone(t.zone_id)}
          >
            ${t.name}
          </button>`
    )}
    </div>`;
  }
  renderSensors() {
    const e = this.requireData();
    return c`
      <section class="page-heading">
        <div>
          <span class="eyebrow">Current readings and configured sources</span>
          <h2>Sensors</h2>
        </div>
        <p>
          See which sources each zone uses and whether current readings are
          available. Missing values are never shown as zero.
        </p>
      </section>
      <section class="sensor-summary">
        <article class="summary-tile">
          <strong>${e.observation.usable_temperature_sources}</strong
          ><span>usable temperature sources</span>
        </article>
        <article class="summary-tile">
          <strong>${e.observation.degraded_zone_count}</strong
          ><span>zones needing attention</span>
        </article>
        <article class="summary-tile">
          <strong
            >${e.observation.collection_active ? "Active" : "Stopped"}</strong
          ><span>observation collection</span>
        </article>
      </section>
      <div class="zone-health-grid">
        ${e.configuration.zones.map((t) => {
      const i = e.snapshot.zones.find(
        (n) => n.zone_id === t.zone_id
      ), a = i?.sensor_data_degraded === !0 || i?.thermostat_data_degraded === !0;
      return c`<article class="card zone-health-card">
            <div class="card-heading">
              <div>
                <span class="eyebrow">Zone</span>
                <h3>${t.name}</h3>
              </div>
              <span class="health-pill ${a ? "warning" : "healthy"}"
                >${a ? "⚠ Review" : "✓ Healthy"}</span
              >
            </div>
            <div class="sensor-reading">
              <strong
                >${this.temperature(i?.effective_temperature_c ?? null)}</strong
              >
              <span
                >${this.humidity(
        i?.effective_humidity_pct ?? null,
        t.humidity_sources.some((n) => n.enabled)
      )}
                humidity</span
              >
            </div>
            <dl class="source-counts">
              <div>
                <dt>Temperature</dt>
                <dd>${this.enabledSourceCount(t.temperature_sources)}</dd>
              </div>
              <div>
                <dt>Humidity</dt>
                <dd>${this.enabledSourceCount(t.humidity_sources)}</dd>
              </div>
              <div>
                <dt>Contacts</dt>
                <dd>
                  ${this.enabledBindingCount(t.window_door_entity_ids)}
                </dd>
              </div>
              <div>
                <dt>Occupancy</dt>
                <dd>${this.enabledBindingCount(t.occupancy_entity_ids)}</dd>
              </div>
              <div>
                <dt>Equipment-stage evidence</dt>
                <dd>${t.stage_entity_ids.length}</dd>
              </div>
              <div>
                <dt>Fan-only control</dt>
                <dd>${this.enabledBindingCount(t.fan_entity_ids)}</dd>
              </div>
            </dl>
            ${i?.sensor_data_degraded === !0 ? c`<p class="warning-copy">Temperature source data is degraded.</p>` : g}
            ${i?.thermostat_data_degraded === !0 ? c`<p class="warning-copy">Thermostat observation data is degraded.</p>` : g}
            ${this.enabledSourceCount(t.humidity_sources) === 0 ? c`<p class="muted">Humidity is not configured for this zone. Reconfigure the zone to select a humidity sensor or thermostat.</p>` : g}
          </article>`;
    })}
      </div>
      <section class="boundary-note">
        <span aria-hidden="true">ⓘ</span>
        <div>
          <strong>History availability</strong>
          <p>${e.observation.history_boundary}</p>
        </div>
      </section>
    `;
  }
  renderActivity() {
    const e = this.requireData(), t = e.activity.records.filter(
      (i) => this.activityFilter === "all" || i.severity === this.activityFilter
    );
    return c`
      <section class="page-heading with-action">
        <div>
          <span class="eyebrow">Newest activity first</span>
          <h2>Activity</h2>
          <p>
            Decisions, observations, transitions, warnings, and lifecycle
            events.
          </p>
        </div>
        <label class="filter"
          ><span>Show</span
          ><select .value=${this.activityFilter} @change=${this.filterChanged}>
            <option value="all">All activity</option>
            <option value="warning">Warnings</option>
            <option value="error">Errors</option>
            <option value="info">Information</option>
          </select></label
        >
      </section>
      <section class="card activity-card">
        <p class="record-count">
          Showing ${t.length} of ${e.activity.total} retained records
        </p>
        ${this.renderActivityRecords(t)}
        ${e.activity.records.length < e.activity.total ? c`<button
                type="button"
                class="load-more"
                ?disabled=${this.activityLoadingOlder}
                @click=${this.loadOlderActivity}
              >
                ${this.activityLoadingOlder ? "Loading…" : "Load older activity"}
              </button>` : g}
      </section>
    `;
  }
  renderActivityRecords(e) {
    return e.length === 0 ? c`<div class="empty-state" role="status">
        No matching material activity is available.
      </div>` : c`<ol class="activity-list">
      ${e.map((t) => {
      const i = this.data?.configuration.zones.find(
        (n) => n.zone_id === t.zone_id
      ), a = this.activityFacts(t);
      return c`<li>
          <span
            class="activity-marker severity-${t.severity}"
            aria-hidden="true"
          ></span>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${U(t.activity_type)}</strong
              ><time datetime=${t.timestamp_utc}
                >${this.time(t.timestamp_utc)}</time
              >
            </div>
            <p>${t.explanation}</p>
            ${a.length === 0 ? g : c`<dl class="activity-facts">
                    ${a.map(
        (n) => c`<div>
                          <dt>${n.label}</dt>
                          <dd>${n.value}</dd>
                        </div>`
      )}
                  </dl>`}
            <div class="activity-meta">
              <span>${U(t.reason_code)}</span
              >${i === void 0 ? g : c`<span>${i.name}</span>`}<span>${t.severity}</span>${this.repairRecordStatus(t)}
            </div>
          </div>
        </li>`;
    })}
    </ol>`;
  }
  activityFacts(e) {
    const t = e.detail;
    switch (e.reason_code) {
      case "control_state_changed":
        return this.transitionFact(
          "State",
          t.previous_state,
          t.new_state
        );
      case "thermostat_mode_changed":
        return this.transitionFact(
          "Mode",
          t.previous_hvac_mode,
          t.new_hvac_mode
        );
      case "thermostat_target_changed":
        return [
          "previous_target_temperature_c",
          "previous_target_low_c",
          "previous_target_high_c",
          "new_target_temperature_c",
          "new_target_low_c",
          "new_target_high_c"
        ].some((i) => Object.hasOwn(t, i)) ? [
          {
            label: "Target",
            value: `${this.activityTarget(t, "previous")} → ${this.activityTarget(t, "new")}`
          }
        ] : [];
      case "source_excluded":
      case "source_exclusion_changed":
      case "source_recovered": {
        const i = this.transitionFact(
          "Quality",
          t.previous_quality,
          t.new_quality
        );
        return t.previous_exclusion_reason !== t.new_exclusion_reason && i.push(
          ...this.transitionFact(
            "Reason",
            t.previous_exclusion_reason,
            t.new_exclusion_reason
          )
        ), i;
      }
      case "migration_failed":
      case "missing_entity":
      case "incompatible_entity":
      case "no_zones_configured":
      case "store_write_failed":
      case "command_boundary_violation":
        return typeof t.issue_code == "string" ? [
          {
            label: "Issue",
            value: U(t.issue_code)
          }
        ] : [];
      default:
        return [];
    }
  }
  transitionFact(e, t, i) {
    return t === void 0 && i === void 0 ? [] : [
      {
        label: e,
        value: `${this.activityValue(t)} → ${this.activityValue(i)}`
      }
    ];
  }
  activityValue(e) {
    return e == null ? "Unavailable" : typeof e != "string" ? String(e) : e === "heat_cool" ? "Heat/Cool" : U(e);
  }
  activityTarget(e, t) {
    const i = e[`${t}_target_temperature_c`], a = e[`${t}_target_low_c`], n = e[`${t}_target_high_c`];
    return typeof a == "number" || typeof n == "number" ? `${this.activityTemperature(a)}–${this.activityTemperature(n)}` : this.activityTemperature(i);
  }
  activityTemperature(e) {
    return ie(
      typeof e == "number" ? e : null,
      this.temperatureUnit(),
      this.locale()
    );
  }
  renderSettings() {
    const e = this.requireData(), t = e.configuration.config.automation_enabled === !0, i = e.configuration.options.safety_limits;
    return c`
      <section class="page-heading">
        <div>
          <span class="eyebrow">Configuration & system health</span>
          <h2>Settings</h2>
        </div>
        <p>
          Manage how information is displayed, review system health, and open
          Home Assistant’s source configuration.
        </p>
      </section>
      <div class="settings-grid">
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">°</span>
          <div>
            <h3>Temperature display</h3>
            <label class="setting-select">
              <span>Use temperatures in</span>
              <select
                .value=${this.temperatureUnitPreference}
                @change=${this.temperatureUnitChanged}
              >
                <option value="home_assistant">Follow Home Assistant</option>
                <option value="fahrenheit">Fahrenheit (°F)</option>
                <option value="celsius">Celsius (°C)</option>
              </select>
            </label>
            <p>
              Applies to temperatures, targets, explanations, and the Today
              timeline in this browser.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">◉</span>
          <div>
            <h3>Automation</h3>
            <p class="setting-value">
              ${t ? "Configured" : "Off"}
            </p>
            <p>
              Observation, activity, and sensor health remain active when
              automation is off.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">⌁</span>
          <div>
            <h3>Safety limits</h3>
            <p class="setting-value">
              ${typeof i == "object" && i !== null ? "Loaded and enforced" : "Unavailable"}
            </p>
            <p>
              Backend validation remains authoritative. The frontend cannot
              lower a gate.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">↺</span>
          <div>
            <h3>History</h3>
            <p class="setting-value">
              ${e.observation.presentation_history_hours} hours local
            </p>
            <p>
              The Today trace is nonauthoritative presentation data, not
              training data.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">⚠</span>
          <div>
            <h3>Repairs</h3>
            <p class="setting-value">
              ${e.configuration.active_repairs.length === 0 ? "No active repairs" : `${String(e.configuration.active_repairs.length)} need attention`}
            </p>
            <p>
              Activity retains historical repair events. Only items currently
              listed here are active now.
            </p>
          </div>
        </section>
      </div>
      <section class="card links-card">
        <h3>Home Assistant tools</h3>
        <div class="settings-links">
          <a href="/config/integrations/integration/intelligent_climate"
            ><span aria-hidden="true">⚙</span>
            <div>
              <strong>Integration configuration</strong
              ><small
                >Select humidity, contact, occupancy, stage, fan, and
                temperature sources by reconfiguring a zone</small
              >
            </div>
            <span aria-hidden="true">→</span></a
          >
          <a href="/config/repairs"
            ><span aria-hidden="true">⚠</span>
            <div>
              <strong>Repairs</strong
              ><small>Review issues requiring attention</small>
            </div>
            <span aria-hidden="true">→</span></a
          >
          <a href="/config/integrations/integration/intelligent_climate"
            ><span aria-hidden="true">⇩</span>
            <div>
              <strong>Download diagnostics</strong
              ><small
                >Open the integration page, then use the entry menu to download
                diagnostics</small
              >
            </div>
            <span aria-hidden="true">→</span></a
          >
        </div>
      </section>
      <section class="boundary-note">
        <span aria-hidden="true">🛡</span>
        <div>
          <strong>Read-only preview</strong>
          <p>
            Observe Only and Shadow information is available here. This release
            cannot send commands to your thermostat or fans.
          </p>
        </div>
      </section>
      <details class="card diagnostics-details">
        <summary>Technical diagnostics</summary>
        <p>
          Frontend ${this.panel.config.frontend_version}; API
          v${this.panel.config.api_version}. Invalid or mismatched data is not
          displayed.
        </p>
      </details>
    `;
  }
  entries() {
    return this.panel.config.entries;
  }
  requireData() {
    if (this.data === void 0)
      throw new Error("panel data is not loaded");
    return this.data;
  }
  selectedZone() {
    return this.data?.configuration.zones.find(
      (e) => e.zone_id === this.selectedZoneId
    );
  }
  selectedZoneSnapshot() {
    return this.data?.snapshot.zones.find(
      (e) => e.zone_id === this.selectedZoneId
    );
  }
  locale() {
    return this.hass.locale.language;
  }
  temperatureUnit() {
    return oi(
      this.temperatureUnitPreference,
      this.hass.config.unit_system.temperature
    );
  }
  temperature(e) {
    return ie(e, this.temperatureUnit(), this.locale());
  }
  humidity(e, t = !0) {
    return t ? e === null ? "Unavailable" : `${new Intl.NumberFormat(this.locale(), { maximumFractionDigits: 1 }).format(e)}%` : "Not configured";
  }
  time(e) {
    return G(e, this.locale(), this.timeline?.time_zone);
  }
  enabledSourceCount(e) {
    return e.filter((t) => t.enabled).length;
  }
  enabledBindingCount(e) {
    return e.filter((t) => t.enabled && t.reviewed).length;
  }
  renderNarrative() {
    const e = this.narrative;
    if (e === void 0)
      return "A current explanation is not available yet.";
    const i = [
      {
        observing: "Intelligent Climate is observing only.",
        manual_idle: "Manual Control is selected and automation is off.",
        shadow_qualifying: "Scheduled Shadow is evaluating conditions without sending commands.",
        shadow_ready: "Scheduled Shadow is ready and is still not sending commands.",
        safe_fallback: "Automatic control is suppressed by Safe Fallback.",
        emergency_paused: "Control is paused.",
        degraded: "Observation is continuing with degraded data.",
        reconciling: "Live state is being checked after startup."
      }[e.control_state] ?? `Current status: ${U(e.control_state)}.`
    ], a = e.effective_target_c ?? e.scheduled_target_c;
    if (a !== null) {
      const n = e.next_transition_utc === null ? "" : ` until ${this.time(e.next_transition_utc)}`;
      i.push(
        `The current target is ${this.temperature(a)}${n}.`
      );
    }
    if (e.temperature_c !== null) {
      const n = e.hvac_action === null ? "" : `, and the thermostat reports ${e.hvac_action}`;
      i.push(
        `The zone is ${this.temperature(e.temperature_c)}${n}.`
      );
    }
    return e.source_degraded && i.push("Some current sensor data needs attention."), i.join(" ");
  }
  repairRecordStatus(e) {
    if (!e.activity_type.startsWith("repair_issue_"))
      return g;
    const t = this.data?.configuration.active_repairs.includes(e.reason_code) === !0;
    return c`<span class=${t ? "repair-active" : "repair-history"}
      >${t ? "Active repair" : "Historical record"}</span
    >`;
  }
  async initialize() {
    if (this.panel.config.api_version !== 1) {
      this.loading = !1, this.errorMessage = `This panel expects API version 1, but received ${String(this.panel.config.api_version)}.`;
      return;
    }
    const e = this.entries()[0];
    if (e === void 0) {
      this.loading = !1, this.errorMessage = "No loaded Intelligent Climate equipment group is available.";
      return;
    }
    this.selectedEntryId = e.entry_id, await this.loadEntry(e.entry_id);
  }
  async loadEntry(e) {
    const t = ++this.loadGeneration;
    this.unsubscribe?.(), this.unsubscribe = void 0, this.loading = !0, this.errorMessage = "", this.data = void 0, this.timeline = void 0, this.narrative = void 0, this.scheduleDocument = void 0, this.schedulePreview = void 0, this.scheduleDirty = !1, this.scheduleMessage = "", this.scheduleConflict = !1;
    const i = new Yt(this.hass, e);
    this.client = i;
    try {
      const a = await i.dashboardData();
      if (t !== this.loadGeneration)
        return;
      this.data = a;
      const n = a.configuration.zones[0];
      if (this.selectedZoneId = n?.zone_id ?? "", this.selectedZoneId.length > 0 && await this.loadZoneDetails(t), this.activeRoute === "schedule" && await this.loadSchedule(t), t !== this.loadGeneration)
        return;
      this.unsubscribe = await i.subscribe((s) => {
        this.applySnapshot(s);
      });
    } catch (a) {
      if (t !== this.loadGeneration)
        return;
      this.errorMessage = this.describeError(a);
    } finally {
      t === this.loadGeneration && (this.loading = !1);
    }
  }
  async loadSchedule(e) {
    if (!(this.client === void 0 || this.data === void 0)) {
      this.scheduleLoading = !0, this.scheduleMessage = "";
      try {
        const t = await this.client.schedule();
        if (e !== this.loadGeneration) return;
        this.scheduleDocument = t.schedule ?? ci(this.selectedEntryId, this.data.configuration), this.schedulePreview = void 0, this.scheduleDirty = !1, this.scheduleConflict = !1;
      } catch (t) {
        if (e !== this.loadGeneration) return;
        this.scheduleDocument = void 0, this.scheduleMessage = this.describeError(t);
      } finally {
        e === this.loadGeneration && (this.scheduleLoading = !1);
      }
    }
  }
  async loadZoneDetails(e) {
    if (this.client === void 0 || this.selectedZoneId.length === 0)
      return;
    const t = ++this.detailLoadGeneration, [i, a] = await Promise.allSettled([
      this.client.todayTimeline(this.selectedZoneId),
      this.client.narrative(this.selectedZoneId)
    ]);
    e !== this.loadGeneration || t !== this.detailLoadGeneration || (this.timeline = i.status === "fulfilled" ? i.value : void 0, this.narrative = a.status === "fulfilled" ? a.value : void 0);
  }
  applySnapshot(e) {
    this.data === void 0 || e.entry_id !== this.selectedEntryId || (this.data = { ...this.data, snapshot: e }, this.loadZoneDetails(this.loadGeneration));
  }
  describeError(e) {
    return e instanceof _ ? `The backend returned data this frontend cannot safely display (${e.message}). Reload the integration or update the candidate.` : e instanceof Error ? e.message : "An unknown local data error occurred.";
  }
  navigate(e) {
    this.confirmDiscard(e) && (this.activeRoute = e, window.history.replaceState(null, "", `/intelligent-climate/${e}`), this.shadowRoot?.querySelector("#main-content")?.focus(), e === "schedule" && this.scheduleDocument === void 0 && this.loadSchedule(this.loadGeneration));
  }
  selectZone(e) {
    this.selectedZoneId = e, this.loadZoneDetails(this.loadGeneration);
  }
  confirmDiscard(e) {
    return !this.scheduleDirty || e === "schedule" ? !0 : window.confirm("Discard unsaved schedule changes?") ? (this.scheduleDocument = void 0, this.schedulePreview = void 0, this.scheduleDirty = !1, this.scheduleMessage = "", this.scheduleConflict = !1, !0) : !1;
  }
  errorCode(e) {
    if (typeof e != "object" || e === null) return;
    const t = e.code;
    return typeof t == "string" ? t : void 0;
  }
  describeScheduleError(e) {
    return this.errorCode(e) === "revision_conflict" ? "The schedule changed in another editor. Your draft was not saved." : this.describeError(e);
  }
};
ne.properties = {
  hass: { attribute: !1 },
  panel: { attribute: !1 },
  route: { attribute: !1 },
  narrow: { type: Boolean },
  activeRoute: { state: !0 },
  selectedEntryId: { state: !0 },
  selectedZoneId: { state: !0 },
  data: { state: !0 },
  timeline: { state: !0 },
  narrative: { state: !0 },
  loading: { state: !0 },
  errorMessage: { state: !0 },
  activityFilter: { state: !0 },
  temperatureUnitPreference: { state: !0 },
  activityLoadingOlder: { state: !0 },
  scheduleDocument: { state: !0 },
  schedulePreview: { state: !0 },
  scheduleLoading: { state: !0 },
  scheduleSaving: { state: !0 },
  scheduleDirty: { state: !0 },
  scheduleMessage: { state: !0 },
  scheduleConflict: { state: !0 }
}, ne.styles = [
  Ve,
  se`
      :host {
        display: block;
        min-block-size: 100%;
      }
      .app-shell {
        min-block-size: 100vh;
        background:
          radial-gradient(
            circle at 80% 0%,
            color-mix(in srgb, var(--ic-accent) 10%, transparent),
            transparent 30%
          ),
          var(--lovelace-background, var(--primary-background-color));
      }
      .topbar {
        min-block-size: 86px;
        padding: 14px clamp(16px, 4vw, 48px);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        background: color-mix(in srgb, var(--ic-surface) 92%, transparent);
        border-block-end: 1px solid var(--ic-border);
        backdrop-filter: blur(18px);
      }
      .schedule-safety {
        border: 1px solid var(--ic-border);
        border-radius: 999px;
        padding: 8px 12px;
        color: var(--secondary-text-color);
        font-weight: 700;
      }
      .schedule-conflict {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        margin-block-end: 16px;
        padding: 16px;
        border: 2px solid var(--warning-color, #f9a825);
        border-radius: 14px;
        background: color-mix(
          in srgb,
          var(--warning-color, #f9a825) 10%,
          var(--ic-surface)
        );
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 14px;
      }
      .brand-mark {
        inline-size: 46px;
        block-size: 46px;
        display: grid;
        place-items: center;
        border-radius: 15px;
        background: linear-gradient(
          145deg,
          var(--ic-accent),
          color-mix(in srgb, var(--ic-accent) 55%, #6c5ce7)
        );
        color: white;
        font-weight: 800;
        letter-spacing: -0.04em;
        box-shadow: 0 8px 22px
          color-mix(in srgb, var(--ic-accent) 30%, transparent);
      }
      h1,
      h2,
      h3,
      p {
        margin-block: 0;
      }
      h1 {
        font-size: clamp(1.1rem, 2vw, 1.35rem);
        letter-spacing: -0.025em;
      }
      .brand p,
      .page-heading p {
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        margin-block-start: 3px;
      }
      .entry-picker {
        display: grid;
        gap: 3px;
        font-size: 0.72rem;
        color: var(--secondary-text-color);
      }
      select {
        min-inline-size: 180px;
        border: 1px solid var(--ic-border);
        border-radius: 12px;
        background: var(--ic-surface);
        padding-inline: 12px 36px;
      }
      .entry-name {
        padding: 10px 14px;
        border-radius: 12px;
        background: var(--ic-surface-muted);
        font-weight: 600;
      }
      .primary-nav {
        position: sticky;
        inset-block-start: 0;
        z-index: 4;
        min-block-size: 62px;
        display: flex;
        justify-content: center;
        gap: 4px;
        padding: 8px 16px;
        background: color-mix(in srgb, var(--ic-surface) 94%, transparent);
        border-block-end: 1px solid var(--ic-border);
        backdrop-filter: blur(16px);
      }
      .primary-nav button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        min-inline-size: 116px;
        border: 0;
        border-radius: 12px;
        background: transparent;
        cursor: pointer;
        font-weight: 600;
        color: var(--secondary-text-color);
      }
      .primary-nav button.active {
        background: color-mix(in srgb, var(--ic-accent) 12%, transparent);
        color: var(--primary-text-color);
        box-shadow: inset 0 -2px var(--ic-accent);
      }
      main {
        max-inline-size: 1480px;
        margin-inline: auto;
        padding: clamp(18px, 3.5vw, 46px);
      }
      .loading {
        min-block-size: 60vh;
        display: grid;
        place-items: center;
        align-content: center;
        gap: 12px;
        color: var(--secondary-text-color);
        text-align: center;
      }
      .loading strong {
        color: var(--primary-text-color);
        font-size: 1.1rem;
      }
      .spinner {
        inline-size: 46px;
        block-size: 46px;
        border-radius: 50%;
        border: 4px solid var(--ic-border);
        border-block-start-color: var(--ic-accent);
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      .error-card {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 20px;
        max-inline-size: 720px;
        margin: 80px auto;
        padding: 30px;
        border: 1px solid
          color-mix(in srgb, var(--error-color, #d93025) 35%, transparent);
        border-radius: var(--ic-radius);
        background: var(--ic-surface);
        box-shadow: var(--ic-shadow);
      }
      .error-icon {
        inline-size: 48px;
        block-size: 48px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        background: color-mix(
          in srgb,
          var(--error-color, #d93025) 15%,
          transparent
        );
        color: var(--error-color, #d93025);
        font-weight: 900;
        font-size: 1.4rem;
      }
      .error-card p {
        margin-block: 8px 20px;
        color: var(--secondary-text-color);
      }
      .primary-button,
      .text-button,
      .icon-button {
        border: 0;
        cursor: pointer;
      }
      .primary-button {
        padding-inline: 18px;
        border-radius: 12px;
        background: var(--ic-accent);
        color: white;
        font-weight: 700;
      }
      .status-hero {
        position: relative;
        overflow: hidden;
        min-block-size: 250px;
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 30px;
        padding: clamp(26px, 5vw, 58px);
        border-radius: 28px;
        color: white;
        background: linear-gradient(
          125deg,
          #1c516a 0%,
          #147aa0 52%,
          #0b96ad 100%
        );
        box-shadow: 0 22px 50px rgb(0 78 105 / 20%);
      }
      .status-hero.tone-warning {
        background: linear-gradient(125deg, #5b3b12, #a26011, #c17d18);
      }
      .status-hero.tone-critical {
        background: linear-gradient(125deg, #651f26, #a52d37, #c64545);
      }
      .status-hero.tone-positive {
        background: linear-gradient(125deg, #154f44, #187761, #249a79);
      }
      .status-hero::before {
        content: "";
        position: absolute;
        inset: -60% -10% auto 50%;
        inline-size: 600px;
        block-size: 600px;
        border: 1px solid rgb(255 255 255 / 18%);
        border-radius: 50%;
      }
      .status-copy {
        position: relative;
        z-index: 1;
        max-inline-size: 760px;
      }
      .eyebrow {
        display: block;
        margin-block-end: 7px;
        font-size: 0.72rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.13em;
        color: var(--secondary-text-color);
      }
      .status-hero .eyebrow {
        color: rgb(255 255 255 / 72%);
      }
      .status-hero h2 {
        font-size: clamp(1.8rem, 4vw, 3.4rem);
        letter-spacing: -0.055em;
        line-height: 1;
      }
      .status-hero p {
        max-inline-size: 690px;
        margin-block: 18px 22px;
        line-height: 1.55;
        color: rgb(255 255 255 / 85%);
      }
      .status-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .status-meta span {
        padding: 6px 10px;
        border-radius: 999px;
        background: rgb(255 255 255 / 12%);
        font-size: 0.75rem;
      }
      .hero-orbit {
        position: relative;
        z-index: 1;
        inline-size: 150px;
        block-size: 150px;
        display: grid;
        place-items: center;
        align-content: center;
        border-radius: 50%;
        background: rgb(255 255 255 / 10%);
        border: 1px solid rgb(255 255 255 / 22%);
      }
      .orbit-ring {
        position: absolute;
        inset: 12px;
        border: 2px dashed rgb(255 255 255 / 35%);
        border-radius: 50%;
      }
      .orbit-value {
        font-size: 2.8rem;
        font-weight: 800;
        line-height: 1;
      }
      .orbit-label {
        font-size: 0.78rem;
        opacity: 0.8;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-block: 18px 28px;
      }
      .metric-card {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 12px;
        min-block-size: 96px;
        padding: 16px;
        border: 1px solid var(--ic-border);
        border-radius: 17px;
        background: var(--ic-surface);
        box-shadow: 0 5px 18px rgb(0 0 0 / 5%);
      }
      .metric-icon {
        inline-size: 42px;
        block-size: 42px;
        display: grid;
        place-items: center;
        border-radius: 13px;
        background: color-mix(in srgb, var(--ic-accent) 12%, transparent);
        color: var(--ic-accent);
        font-weight: 800;
      }
      .metric-icon.humidity {
        color: #5b6ee1;
        background: rgb(91 110 225 / 12%);
      }
      .metric-icon.source {
        color: #18815f;
        background: rgb(24 129 95 / 12%);
      }
      .metric-icon.history {
        color: #ad6a13;
        background: rgb(173 106 19 / 12%);
      }
      .metric-card div span {
        display: block;
        color: var(--secondary-text-color);
        font-size: 0.72rem;
      }
      .metric-card div strong {
        display: block;
        margin-block-start: 4px;
        font-size: 0.87rem;
      }
      .metric-card b {
        font-size: 1.25rem;
      }
      .zone-tabs {
        display: flex;
        gap: 8px;
        margin-block-end: 18px;
        overflow-x: auto;
      }
      .zone-tabs button {
        padding-inline: 18px;
        border: 1px solid var(--ic-border);
        border-radius: 999px;
        background: var(--ic-surface);
        cursor: pointer;
        white-space: nowrap;
      }
      .zone-tabs button.active {
        color: white;
        border-color: var(--ic-accent);
        background: var(--ic-accent);
        font-weight: 700;
      }
      .overview-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
        gap: 18px;
      }
      .card {
        padding: clamp(20px, 3vw, 30px);
        border: 1px solid var(--ic-border);
        border-radius: var(--ic-radius);
        background: var(--ic-surface);
        box-shadow: var(--ic-shadow);
      }
      .card-heading {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 18px;
        margin-block-end: 18px;
      }
      .card-heading h2 {
        font-size: 1.18rem;
        letter-spacing: -0.02em;
      }
      .card-heading h3 {
        font-size: 1.05rem;
      }
      .icon-button {
        inline-size: 44px;
        border-radius: 12px;
        background: var(--ic-surface-muted);
        font-size: 1.2rem;
      }
      .narrative {
        font-size: clamp(1.05rem, 1.8vw, 1.35rem);
        line-height: 1.65;
        letter-spacing: -0.015em;
      }
      .fact-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-block-start: 20px;
      }
      .fact-chips span,
      .activity-meta span {
        padding: 5px 9px;
        border: 1px solid var(--ic-border);
        border-radius: 999px;
        color: var(--secondary-text-color);
        font-size: 0.7rem;
        text-transform: capitalize;
      }
      .muted {
        color: var(--secondary-text-color);
        line-height: 1.5;
      }
      .readiness-state,
      .health-pill {
        padding: 7px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 800;
        white-space: nowrap;
      }
      .readiness-state.waiting {
        color: #a35e0b;
        background: rgb(210 125 16 / 13%);
      }
      .readiness-state.ready,
      .health-pill.healthy {
        color: #137255;
        background: rgb(24 129 95 / 13%);
      }
      .health-pill.warning {
        color: #a35e0b;
        background: rgb(210 125 16 / 13%);
      }
      .progress-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.82rem;
      }
      .progress {
        overflow: hidden;
        block-size: 9px;
        margin-block: 8px 20px;
        border-radius: 999px;
        background: var(--ic-surface-muted);
      }
      .progress span {
        display: block;
        block-size: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, var(--ic-accent), #2ec39b);
      }
      .readiness-facts,
      .source-counts {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        margin: 0;
      }
      .readiness-facts div,
      .source-counts div {
        padding: 12px;
        border-radius: 12px;
        background: var(--ic-surface-muted);
      }
      dt {
        color: var(--secondary-text-color);
        font-size: 0.7rem;
      }
      dd {
        margin: 4px 0 0;
        font-weight: 700;
      }
      .blocking,
      .fault {
        margin-block-start: 14px;
        font-size: 0.78rem;
        color: var(--secondary-text-color);
      }
      .fault {
        color: var(--error-color, #d93025);
      }
      .timeline-card,
      .activity-preview {
        margin-block-start: 18px;
      }
      .provenance-note {
        color: var(--secondary-text-color);
        font-size: 0.76rem;
      }
      .text-button {
        padding-inline: 12px;
        border-radius: 10px;
        background: transparent;
        color: var(--ic-accent);
        font-weight: 700;
      }
      .page-heading {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 24px;
        margin-block: 8px 28px;
      }
      .page-heading h2 {
        font-size: clamp(1.8rem, 4vw, 2.8rem);
        letter-spacing: -0.05em;
      }
      .page-heading p {
        max-inline-size: 630px;
        line-height: 1.5;
      }
      .sensor-summary {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
        margin-block-end: 18px;
      }
      .summary-tile {
        display: grid;
        gap: 4px;
        padding: 20px;
        border-radius: 16px;
        background: var(--ic-surface-muted);
      }
      .summary-tile strong {
        font-size: 1.55rem;
      }
      .summary-tile span {
        color: var(--secondary-text-color);
        font-size: 0.8rem;
      }
      .zone-health-grid,
      .settings-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
      }
      .sensor-reading {
        display: flex;
        align-items: baseline;
        gap: 12px;
        margin-block: 10px 18px;
      }
      .sensor-reading strong {
        font-size: 2rem;
        letter-spacing: -0.04em;
      }
      .sensor-reading span {
        color: var(--secondary-text-color);
      }
      .source-counts {
        grid-template-columns: repeat(5, 1fr);
      }
      .source-counts div {
        text-align: center;
        padding: 10px 5px;
      }
      .warning-copy {
        margin-block-start: 12px;
        color: #a35e0b;
        font-size: 0.8rem;
      }
      .boundary-note {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 14px;
        margin-block-start: 18px;
        padding: 18px 20px;
        border: 1px solid
          color-mix(in srgb, var(--ic-accent) 24%, var(--ic-border));
        border-radius: 15px;
        background: color-mix(in srgb, var(--ic-accent) 7%, var(--ic-surface));
      }
      .boundary-note > span {
        font-size: 1.35rem;
      }
      .boundary-note p {
        margin-block-start: 4px;
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        line-height: 1.45;
      }
      .filter {
        display: grid;
        gap: 4px;
        color: var(--secondary-text-color);
        font-size: 0.72rem;
      }
      .record-count {
        margin-block-end: 20px;
        color: var(--secondary-text-color);
        font-size: 0.78rem;
      }
      .activity-list {
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .load-more {
        min-block-size: 44px;
        display: block;
        margin: 18px auto 0;
        padding-inline: 18px;
        border: 1px solid var(--ic-border);
        border-radius: 12px;
        background: var(--ic-surface-muted);
        color: var(--primary-text-color);
        font: inherit;
        font-weight: 650;
        cursor: pointer;
      }
      .load-more:disabled {
        cursor: wait;
        opacity: 0.65;
      }
      .activity-list li {
        display: grid;
        grid-template-columns: 16px 1fr;
        gap: 12px;
        position: relative;
        padding-block: 2px 22px;
      }
      .activity-list li:not(:last-child)::before {
        content: "";
        position: absolute;
        inset-inline-start: 6px;
        inset-block: 16px 0;
        inline-size: 2px;
        background: var(--ic-border);
      }
      .activity-marker {
        position: relative;
        z-index: 1;
        inline-size: 14px;
        block-size: 14px;
        margin-block-start: 4px;
        border: 3px solid var(--ic-surface);
        border-radius: 50%;
        background: var(--ic-accent);
        box-shadow: 0 0 0 1px var(--ic-accent);
      }
      .activity-marker.severity-warning {
        background: #d17c0d;
        box-shadow: 0 0 0 1px #d17c0d;
      }
      .activity-marker.severity-error {
        background: var(--error-color, #d93025);
        box-shadow: 0 0 0 1px var(--error-color, #d93025);
      }
      .activity-title {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        text-transform: capitalize;
      }
      .activity-title time {
        color: var(--secondary-text-color);
        font-size: 0.76rem;
        white-space: nowrap;
      }
      .activity-body p {
        margin-block: 6px 10px;
        color: var(--secondary-text-color);
        font-size: 0.85rem;
        line-height: 1.5;
      }
      .activity-facts {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 0 0 10px;
      }
      .activity-facts div {
        display: inline-flex;
        gap: 5px;
        padding: 6px 9px;
        border-radius: 8px;
        background: var(--ic-surface-muted);
        font-size: 0.76rem;
      }
      .activity-facts dt {
        color: var(--secondary-text-color);
      }
      .activity-facts dt::after {
        content: ":";
      }
      .activity-facts dd {
        margin: 0;
        font-weight: 650;
      }
      .activity-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .repair-active,
      .repair-history {
        border-radius: 999px;
        padding: 2px 8px;
        font-weight: 650;
      }
      .repair-active {
        background: color-mix(in srgb, var(--error-color) 14%, transparent);
        color: var(--error-color);
      }
      .repair-history {
        background: var(--ic-surface-muted);
      }
      .empty-state {
        min-block-size: 180px;
        display: grid;
        place-items: center;
        color: var(--secondary-text-color);
        text-align: center;
      }
      .setting-card {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 16px;
      }
      .setting-icon {
        inline-size: 44px;
        block-size: 44px;
        display: grid;
        place-items: center;
        border-radius: 13px;
        background: color-mix(in srgb, var(--ic-accent) 12%, transparent);
        color: var(--ic-accent);
        font-size: 1.2rem;
      }
      .setting-card h3 {
        font-size: 1rem;
      }
      .setting-card p {
        margin-block-start: 7px;
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        line-height: 1.45;
      }
      .setting-card .setting-value {
        color: var(--primary-text-color);
        font-weight: 700;
      }
      .setting-select {
        display: grid;
        gap: 6px;
        margin-block: 8px;
        color: var(--secondary-text-color);
        font-size: 0.82rem;
      }
      .setting-select select {
        inline-size: 100%;
      }
      .diagnostics-details {
        margin-block-start: 18px;
      }
      .diagnostics-details p {
        color: var(--secondary-text-color);
        padding-block-start: 10px;
      }
      .links-card {
        margin-block-start: 18px;
      }
      .settings-links {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin-block-start: 16px;
      }
      .settings-links a {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 12px;
        padding: 14px;
        border: 1px solid var(--ic-border);
        border-radius: 13px;
        color: inherit;
        text-decoration: none;
      }
      .settings-links a:hover {
        border-color: var(--ic-accent);
        background: color-mix(in srgb, var(--ic-accent) 5%, transparent);
      }
      .settings-links small {
        display: block;
        margin-block-start: 3px;
        color: var(--secondary-text-color);
      }
      @media (max-width: 980px) {
        .metric-grid {
          grid-template-columns: repeat(2, 1fr);
        }
        .overview-grid {
          grid-template-columns: 1fr;
        }
        .source-counts {
          grid-template-columns: repeat(3, 1fr);
        }
        .settings-links {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 700px) {
        .topbar {
          align-items: flex-start;
        }
        .brand p {
          display: none;
        }
        .entry-name {
          display: none;
        }
        .primary-nav {
          justify-content: stretch;
          overflow-x: auto;
        }
        .primary-nav button {
          min-inline-size: 88px;
          flex: 1;
          flex-direction: column;
          gap: 2px;
          font-size: 0.72rem;
        }
        main {
          padding: 16px;
        }
        .status-hero {
          grid-template-columns: 1fr;
          min-block-size: auto;
          border-radius: 22px;
        }
        .hero-orbit {
          display: none;
        }
        .status-hero h2 {
          font-size: 2rem;
        }
        .metric-grid,
        .sensor-summary,
        .zone-health-grid,
        .settings-grid {
          grid-template-columns: 1fr;
        }
        .metric-card {
          min-block-size: 82px;
        }
        .page-heading,
        .page-heading.with-action {
          align-items: stretch;
          flex-direction: column;
        }
        .source-counts {
          grid-template-columns: repeat(2, 1fr);
        }
        .card {
          padding: 20px;
        }
        .activity-title {
          flex-direction: column;
          gap: 3px;
        }
      }
      @media (max-width: 380px) {
        .topbar {
          padding-inline: 12px;
        }
        .brand-mark {
          inline-size: 40px;
          block-size: 40px;
        }
        .brand h1 {
          font-size: 1rem;
        }
        .entry-picker select {
          min-inline-size: 130px;
          max-inline-size: 150px;
        }
        .metric-card {
          grid-template-columns: auto 1fr;
        }
        .metric-card b {
          grid-column: 2;
        }
      }
    `
];
let ve = ne;
customElements.get("intelligent-climate-panel") || customElements.define("intelligent-climate-panel", ve);
