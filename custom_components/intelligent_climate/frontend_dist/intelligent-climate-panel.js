const B = globalThis, ce = B.ShadowRoot && (B.ShadyCSS === void 0 || B.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, le = /* @__PURE__ */ Symbol(), me = /* @__PURE__ */ new WeakMap();
let Ae = class {
  constructor(e, t, i) {
    if (this._$cssResult$ = !0, i !== le) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = e, this.t = t;
  }
  get styleSheet() {
    let e = this.o;
    const t = this.t;
    if (ce && e === void 0) {
      const i = t !== void 0 && t.length === 1;
      i && (e = me.get(t)), e === void 0 && ((this.o = e = new CSSStyleSheet()).replaceSync(this.cssText), i && me.set(t, e));
    }
    return e;
  }
  toString() {
    return this.cssText;
  }
};
const Me = (a) => new Ae(typeof a == "string" ? a : a + "", void 0, le), de = (a, ...e) => {
  const t = a.length === 1 ? a[0] : e.reduce((i, r, n) => i + ((s) => {
    if (s._$cssResult$ === !0) return s.cssText;
    if (typeof s == "number") return s;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + s + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(r) + a[n + 1], a[0]);
  return new Ae(t, a, le);
}, Ie = (a, e) => {
  if (ce) a.adoptedStyleSheets = e.map((t) => t instanceof CSSStyleSheet ? t : t.styleSheet);
  else for (const t of e) {
    const i = document.createElement("style"), r = B.litNonce;
    r !== void 0 && i.setAttribute("nonce", r), i.textContent = t.cssText, a.appendChild(i);
  }
}, ge = ce ? (a) => a : (a) => a instanceof CSSStyleSheet ? ((e) => {
  let t = "";
  for (const i of e.cssRules) t += i.cssText;
  return Me(t);
})(a) : a;
const { is: Ne, defineProperty: He, getOwnPropertyDescriptor: De, getOwnPropertyNames: Le, getOwnPropertySymbols: qe, getPrototypeOf: Fe } = Object, Q = globalThis, ve = Q.trustedTypes, Ze = ve ? ve.emptyScript : "", je = Q.reactiveElementPolyfillSupport, M = (a, e) => a, ie = { toAttribute(a, e) {
  switch (e) {
    case Boolean:
      a = a ? Ze : null;
      break;
    case Object:
    case Array:
      a = a == null ? a : JSON.stringify(a);
  }
  return a;
}, fromAttribute(a, e) {
  let t = a;
  switch (e) {
    case Boolean:
      t = a !== null;
      break;
    case Number:
      t = a === null ? null : Number(a);
      break;
    case Object:
    case Array:
      try {
        t = JSON.parse(a);
      } catch {
        t = null;
      }
  }
  return t;
} }, Ee = (a, e) => !Ne(a, e), fe = { attribute: !0, type: String, converter: ie, reflect: !1, useDefault: !1, hasChanged: Ee };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), Q.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let C = class extends HTMLElement {
  static addInitializer(e) {
    this._$Ei(), (this.l ??= []).push(e);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(e, t = fe) {
    if (t.state && (t.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(e) && ((t = Object.create(t)).wrapped = !0), this.elementProperties.set(e, t), !t.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), r = this.getPropertyDescriptor(e, i, t);
      r !== void 0 && He(this.prototype, e, r);
    }
  }
  static getPropertyDescriptor(e, t, i) {
    const { get: r, set: n } = De(this.prototype, e) ?? { get() {
      return this[t];
    }, set(s) {
      this[t] = s;
    } };
    return { get: r, set(s) {
      const h = r?.call(this);
      n?.call(this, s), this.requestUpdate(e, h, i);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(e) {
    return this.elementProperties.get(e) ?? fe;
  }
  static _$Ei() {
    if (this.hasOwnProperty(M("elementProperties"))) return;
    const e = Fe(this);
    e.finalize(), e.l !== void 0 && (this.l = [...e.l]), this.elementProperties = new Map(e.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(M("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(M("properties"))) {
      const t = this.properties, i = [...Le(t), ...qe(t)];
      for (const r of i) this.createProperty(r, t[r]);
    }
    const e = this[Symbol.metadata];
    if (e !== null) {
      const t = litPropertyMetadata.get(e);
      if (t !== void 0) for (const [i, r] of t) this.elementProperties.set(i, r);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [t, i] of this.elementProperties) {
      const r = this._$Eu(t, i);
      r !== void 0 && this._$Eh.set(r, t);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(e) {
    const t = [];
    if (Array.isArray(e)) {
      const i = new Set(e.flat(1 / 0).reverse());
      for (const r of i) t.unshift(ge(r));
    } else e !== void 0 && t.push(ge(e));
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
    return Ie(e, this.constructor.elementStyles), e;
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
    const i = this.constructor.elementProperties.get(e), r = this.constructor._$Eu(e, i);
    if (r !== void 0 && i.reflect === !0) {
      const n = (i.converter?.toAttribute !== void 0 ? i.converter : ie).toAttribute(t, i.type);
      this._$Em = e, n == null ? this.removeAttribute(r) : this.setAttribute(r, n), this._$Em = null;
    }
  }
  _$AK(e, t) {
    const i = this.constructor, r = i._$Eh.get(e);
    if (r !== void 0 && this._$Em !== r) {
      const n = i.getPropertyOptions(r), s = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : ie;
      this._$Em = r;
      const h = s.fromAttribute(t, n.type);
      this[r] = h ?? this._$Ej?.get(r) ?? h, this._$Em = null;
    }
  }
  requestUpdate(e, t, i, r = !1, n) {
    if (e !== void 0) {
      const s = this.constructor;
      if (r === !1 && (n = this[e]), i ??= s.getPropertyOptions(e), !((i.hasChanged ?? Ee)(n, t) || i.useDefault && i.reflect && n === this._$Ej?.get(e) && !this.hasAttribute(s._$Eu(e, i)))) return;
      this.C(e, t, i);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(e, t, { useDefault: i, reflect: r, wrapped: n }, s) {
    i && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(e) && (this._$Ej.set(e, s ?? t ?? this[e]), n !== !0 || s !== void 0) || (this._$AL.has(e) || (this.hasUpdated || i || (t = void 0), this._$AL.set(e, t)), r === !0 && this._$Em !== e && (this._$Eq ??= /* @__PURE__ */ new Set()).add(e));
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
        for (const [r, n] of this._$Ep) this[r] = n;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [r, n] of i) {
        const { wrapped: s } = n, h = this[r];
        s !== !0 || this._$AL.has(r) || h === void 0 || this.C(r, void 0, n, h);
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
C.elementStyles = [], C.shadowRootOptions = { mode: "open" }, C[M("elementProperties")] = /* @__PURE__ */ new Map(), C[M("finalized")] = /* @__PURE__ */ new Map(), je?.({ ReactiveElement: C }), (Q.reactiveElementVersions ??= []).push("2.1.2");
const pe = globalThis, _e = (a) => a, W = pe.trustedTypes, ye = W ? W.createPolicy("lit-html", { createHTML: (a) => a }) : void 0, Ce = "$lit$", k = `lit$${Math.random().toFixed(9).slice(2)}$`, Oe = "?" + k, Be = `<${Oe}>`, A = document, H = () => A.createComment(""), D = (a) => a === null || typeof a != "object" && typeof a != "function", ue = Array.isArray, Ge = (a) => ue(a) || typeof a?.[Symbol.iterator] == "function", ee = `[ 	
\f\r]`, U = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, be = /-->/g, xe = />/g, S = RegExp(`>|${ee}(?:([^\\s"'>=/]+)(${ee}*=${ee}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), $e = /'/g, we = /"/g, Te = /^(?:script|style|textarea|title)$/i, Ve = (a) => (e, ...t) => ({ _$litType$: a, strings: e, values: t }), c = Ve(1), T = /* @__PURE__ */ Symbol.for("lit-noChange"), p = /* @__PURE__ */ Symbol.for("lit-nothing"), ke = /* @__PURE__ */ new WeakMap(), z = A.createTreeWalker(A, 129);
function Pe(a, e) {
  if (!ue(a) || !a.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return ye !== void 0 ? ye.createHTML(e) : e;
}
const We = (a, e) => {
  const t = a.length - 1, i = [];
  let r, n = e === 2 ? "<svg>" : e === 3 ? "<math>" : "", s = U;
  for (let h = 0; h < t; h++) {
    const l = a[h];
    let o, u, m = -1, _ = 0;
    for (; _ < l.length && (s.lastIndex = _, u = s.exec(l), u !== null); ) _ = s.lastIndex, s === U ? u[1] === "!--" ? s = be : u[1] !== void 0 ? s = xe : u[2] !== void 0 ? (Te.test(u[2]) && (r = RegExp("</" + u[2], "g")), s = S) : u[3] !== void 0 && (s = S) : s === S ? u[0] === ">" ? (s = r ?? U, m = -1) : u[1] === void 0 ? m = -2 : (m = s.lastIndex - u[2].length, o = u[1], s = u[3] === void 0 ? S : u[3] === '"' ? we : $e) : s === we || s === $e ? s = S : s === be || s === xe ? s = U : (s = S, r = void 0);
    const $ = s === S && a[h + 1].startsWith("/>") ? " " : "";
    n += s === U ? l + Be : m >= 0 ? (i.push(o), l.slice(0, m) + Ce + l.slice(m) + k + $) : l + k + (m === -2 ? h : $);
  }
  return [Pe(a, n + (a[t] || "<?>") + (e === 2 ? "</svg>" : e === 3 ? "</math>" : "")), i];
};
class L {
  constructor({ strings: e, _$litType$: t }, i) {
    let r;
    this.parts = [];
    let n = 0, s = 0;
    const h = e.length - 1, l = this.parts, [o, u] = We(e, t);
    if (this.el = L.createElement(o, i), z.currentNode = this.el.content, t === 2 || t === 3) {
      const m = this.el.content.firstChild;
      m.replaceWith(...m.childNodes);
    }
    for (; (r = z.nextNode()) !== null && l.length < h; ) {
      if (r.nodeType === 1) {
        if (r.hasAttributes()) for (const m of r.getAttributeNames()) if (m.endsWith(Ce)) {
          const _ = u[s++], $ = r.getAttribute(m).split(k), Z = /([.?@])?(.*)/.exec(_);
          l.push({ type: 1, index: n, name: Z[2], strings: $, ctor: Z[1] === "." ? Je : Z[1] === "?" ? Qe : Z[1] === "@" ? Ye : Y }), r.removeAttribute(m);
        } else m.startsWith(k) && (l.push({ type: 6, index: n }), r.removeAttribute(m));
        if (Te.test(r.tagName)) {
          const m = r.textContent.split(k), _ = m.length - 1;
          if (_ > 0) {
            r.textContent = W ? W.emptyScript : "";
            for (let $ = 0; $ < _; $++) r.append(m[$], H()), z.nextNode(), l.push({ type: 2, index: ++n });
            r.append(m[_], H());
          }
        }
      } else if (r.nodeType === 8) if (r.data === Oe) l.push({ type: 2, index: n });
      else {
        let m = -1;
        for (; (m = r.data.indexOf(k, m + 1)) !== -1; ) l.push({ type: 7, index: n }), m += k.length - 1;
      }
      n++;
    }
  }
  static createElement(e, t) {
    const i = A.createElement("template");
    return i.innerHTML = e, i;
  }
}
function P(a, e, t = a, i) {
  if (e === T) return e;
  let r = i !== void 0 ? t._$Co?.[i] : t._$Cl;
  const n = D(e) ? void 0 : e._$litDirective$;
  return r?.constructor !== n && (r?._$AO?.(!1), n === void 0 ? r = void 0 : (r = new n(a), r._$AT(a, t, i)), i !== void 0 ? (t._$Co ??= [])[i] = r : t._$Cl = r), r !== void 0 && (e = P(a, r._$AS(a, e.values), r, i)), e;
}
class Ke {
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
    const { el: { content: t }, parts: i } = this._$AD, r = (e?.creationScope ?? A).importNode(t, !0);
    z.currentNode = r;
    let n = z.nextNode(), s = 0, h = 0, l = i[0];
    for (; l !== void 0; ) {
      if (s === l.index) {
        let o;
        l.type === 2 ? o = new F(n, n.nextSibling, this, e) : l.type === 1 ? o = new l.ctor(n, l.name, l.strings, this, e) : l.type === 6 && (o = new Xe(n, this, e)), this._$AV.push(o), l = i[++h];
      }
      s !== l?.index && (n = z.nextNode(), s++);
    }
    return z.currentNode = A, r;
  }
  p(e) {
    let t = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(e, i, t), t += i.strings.length - 2) : i._$AI(e[t])), t++;
  }
}
class F {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(e, t, i, r) {
    this.type = 2, this._$AH = p, this._$AN = void 0, this._$AA = e, this._$AB = t, this._$AM = i, this.options = r, this._$Cv = r?.isConnected ?? !0;
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
    e = P(this, e, t), D(e) ? e === p || e == null || e === "" ? (this._$AH !== p && this._$AR(), this._$AH = p) : e !== this._$AH && e !== T && this._(e) : e._$litType$ !== void 0 ? this.$(e) : e.nodeType !== void 0 ? this.T(e) : Ge(e) ? this.k(e) : this._(e);
  }
  O(e) {
    return this._$AA.parentNode.insertBefore(e, this._$AB);
  }
  T(e) {
    this._$AH !== e && (this._$AR(), this._$AH = this.O(e));
  }
  _(e) {
    this._$AH !== p && D(this._$AH) ? this._$AA.nextSibling.data = e : this.T(A.createTextNode(e)), this._$AH = e;
  }
  $(e) {
    const { values: t, _$litType$: i } = e, r = typeof i == "number" ? this._$AC(e) : (i.el === void 0 && (i.el = L.createElement(Pe(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === r) this._$AH.p(t);
    else {
      const n = new Ke(r, this), s = n.u(this.options);
      n.p(t), this.T(s), this._$AH = n;
    }
  }
  _$AC(e) {
    let t = ke.get(e.strings);
    return t === void 0 && ke.set(e.strings, t = new L(e)), t;
  }
  k(e) {
    ue(this._$AH) || (this._$AH = [], this._$AR());
    const t = this._$AH;
    let i, r = 0;
    for (const n of e) r === t.length ? t.push(i = new F(this.O(H()), this.O(H()), this, this.options)) : i = t[r], i._$AI(n), r++;
    r < t.length && (this._$AR(i && i._$AB.nextSibling, r), t.length = r);
  }
  _$AR(e = this._$AA.nextSibling, t) {
    for (this._$AP?.(!1, !0, t); e !== this._$AB; ) {
      const i = _e(e).nextSibling;
      _e(e).remove(), e = i;
    }
  }
  setConnected(e) {
    this._$AM === void 0 && (this._$Cv = e, this._$AP?.(e));
  }
}
class Y {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(e, t, i, r, n) {
    this.type = 1, this._$AH = p, this._$AN = void 0, this.element = e, this.name = t, this._$AM = r, this.options = n, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = p;
  }
  _$AI(e, t = this, i, r) {
    const n = this.strings;
    let s = !1;
    if (n === void 0) e = P(this, e, t, 0), s = !D(e) || e !== this._$AH && e !== T, s && (this._$AH = e);
    else {
      const h = e;
      let l, o;
      for (e = n[0], l = 0; l < n.length - 1; l++) o = P(this, h[i + l], t, l), o === T && (o = this._$AH[l]), s ||= !D(o) || o !== this._$AH[l], o === p ? e = p : e !== p && (e += (o ?? "") + n[l + 1]), this._$AH[l] = o;
    }
    s && !r && this.j(e);
  }
  j(e) {
    e === p ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, e ?? "");
  }
}
class Je extends Y {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(e) {
    this.element[this.name] = e === p ? void 0 : e;
  }
}
class Qe extends Y {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(e) {
    this.element.toggleAttribute(this.name, !!e && e !== p);
  }
}
class Ye extends Y {
  constructor(e, t, i, r, n) {
    super(e, t, i, r, n), this.type = 5;
  }
  _$AI(e, t = this) {
    if ((e = P(this, e, t, 0) ?? p) === T) return;
    const i = this._$AH, r = e === p && i !== p || e.capture !== i.capture || e.once !== i.once || e.passive !== i.passive, n = e !== p && (i === p || r);
    r && this.element.removeEventListener(this.name, this, i), n && this.element.addEventListener(this.name, this, e), this._$AH = e;
  }
  handleEvent(e) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, e) : this._$AH.handleEvent(e);
  }
}
class Xe {
  constructor(e, t, i) {
    this.element = e, this.type = 6, this._$AN = void 0, this._$AM = t, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(e) {
    P(this, e);
  }
}
const et = pe.litHtmlPolyfillSupport;
et?.(L, F), (pe.litHtmlVersions ??= []).push("3.3.3");
const tt = (a, e, t) => {
  const i = t?.renderBefore ?? e;
  let r = i._$litPart$;
  if (r === void 0) {
    const n = t?.renderBefore ?? null;
    i._$litPart$ = r = new F(e.insertBefore(H(), n), n, void 0, t ?? {});
  }
  return r._$AI(a), r;
};
const he = globalThis;
class O extends C {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const e = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= e.firstChild, e;
  }
  update(e) {
    const t = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(e), this._$Do = tt(t, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return T;
  }
}
O._$litElement$ = !0, O.finalized = !0, he.litElementHydrateSupport?.({ LitElement: O });
const it = he.litElementPolyfillSupport;
it?.({ LitElement: O });
(he.litElementVersions ??= []).push("4.2.2");
const at = {
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
function rt(a) {
  return at[a] ?? {
    label: a.replaceAll("_", " "),
    icon: "●",
    tone: "neutral",
    automationOff: !1
  };
}
function ae(a, e, t) {
  if (a === null)
    return "Unavailable";
  const i = e === "°F" ? a * 9 / 5 + 32 : a;
  return `${new Intl.NumberFormat(t, { maximumFractionDigits: 1 }).format(i)}${e}`;
}
function R(a, e, t) {
  return new Intl.DateTimeFormat(e, {
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    day: "numeric",
    ...t === void 0 ? {} : { timeZone: t }
  }).format(new Date(a));
}
function j(a) {
  return a.split("_").filter((e) => e.length > 0).map((e) => e.charAt(0).toUpperCase() + e.slice(1)).join(" ");
}
const b = 1;
class v extends Error {
  constructor(e, t) {
    super(`${e}: ${t}`), this.name = "FrontendContractError";
  }
}
const nt = /* @__PURE__ */ new Set([
  "measured",
  "configured",
  "calculated",
  "forecast",
  "predicted",
  "planned"
]);
function g(a, e) {
  if (typeof a != "object" || a === null || Array.isArray(a))
    throw new v(e, "expected object");
  return a;
}
function x(a, e) {
  if (!Array.isArray(a))
    throw new v(e, "expected array");
  return a;
}
function d(a, e) {
  if (typeof a != "string" || a.length === 0)
    throw new v(e, "expected non-empty string");
  return a;
}
function X(a, e) {
  return a === null ? null : d(a, e);
}
function w(a, e) {
  if (typeof a != "boolean")
    throw new v(e, "expected boolean");
  return a;
}
function I(a, e) {
  if (typeof a != "number" || !Number.isFinite(a))
    throw new v(e, "expected finite number");
  return a;
}
function y(a, e) {
  const t = I(a, e);
  if (!Number.isInteger(t) || t < 0)
    throw new v(e, "expected non-negative integer");
  return t;
}
function N(a, e) {
  return a === null ? null : I(a, e);
}
function f(a, e) {
  const t = d(a, e);
  if (!Number.isFinite(Date.parse(t)))
    throw new v(e, "expected ISO timestamp");
  return t;
}
function E(a, e) {
  if (a.api_version !== b)
    throw new v(
      `${e}.api_version`,
      `expected ${String(b)}`
    );
}
function q(a, e) {
  return x(a, e).map(
    (t, i) => d(t, `${e}[${String(i)}]`)
  );
}
function st(a, e) {
  const t = g(a, e), i = (n, s) => x(n, s).map((h, l) => {
    const o = `${s}[${String(l)}]`, u = g(h, o);
    return {
      entity_id: d(u.entity_id, `${o}.entity_id`),
      enabled: w(u.enabled, `${o}.enabled`)
    };
  }), r = (n, s) => x(n, s).map((h, l) => {
    const o = `${s}[${String(l)}]`, u = g(h, o);
    return {
      entity_id: d(u.entity_id, `${o}.entity_id`),
      enabled: w(u.enabled, `${o}.enabled`),
      reviewed: w(u.reviewed, `${o}.reviewed`)
    };
  });
  return {
    ...t,
    zone_id: d(t.zone_id, `${e}.zone_id`),
    name: d(t.name, `${e}.name`),
    temperature_sources: i(
      t.temperature_sources,
      `${e}.temperature_sources`
    ),
    humidity_sources: i(
      t.humidity_sources,
      `${e}.humidity_sources`
    ),
    window_door_entity_ids: r(
      t.window_door_entity_ids,
      `${e}.window_door_entity_ids`
    ),
    occupancy_entity_ids: r(
      t.occupancy_entity_ids,
      `${e}.occupancy_entity_ids`
    ),
    stage_entity_ids: q(
      t.stage_entity_ids,
      `${e}.stage_entity_ids`
    ),
    fan_entity_ids: r(t.fan_entity_ids, `${e}.fan_entity_ids`)
  };
}
function ot(a) {
  const e = g(a, "config");
  return E(e, "config"), {
    api_version: b,
    config: g(e.config, "config.config"),
    options: g(e.options, "config.options"),
    active_repairs: q(e.active_repairs, "config.active_repairs"),
    zones: x(e.zones, "config.zones").map(
      (t, i) => st(t, `config.zones[${String(i)}]`)
    )
  };
}
function ct(a, e) {
  const t = g(a, e);
  return {
    zone_id: d(t.zone_id, `${e}.zone_id`),
    effective_temperature_c: N(
      t.effective_temperature_c,
      `${e}.effective_temperature_c`
    ),
    effective_humidity_pct: N(
      t.effective_humidity_pct,
      `${e}.effective_humidity_pct`
    ),
    sensor_data_degraded: w(
      t.sensor_data_degraded,
      `${e}.sensor_data_degraded`
    ),
    thermostat_data_degraded: w(
      t.thermostat_data_degraded,
      `${e}.thermostat_data_degraded`
    )
  };
}
function Se(a) {
  const e = g(a, "snapshot");
  return E(e, "snapshot"), {
    api_version: b,
    entry_id: d(e.entry_id, "snapshot.entry_id"),
    observation_revision: y(
      e.observation_revision,
      "snapshot.observation_revision"
    ),
    calculated_at_utc: f(
      e.calculated_at_utc,
      "snapshot.calculated_at_utc"
    ),
    control_state: d(e.control_state, "snapshot.control_state"),
    reason_code: X(e.reason_code, "snapshot.reason_code"),
    zones: x(e.zones, "snapshot.zones").map(
      (t, i) => ct(t, `snapshot.zones[${String(i)}]`)
    )
  };
}
function lt(a, e) {
  const t = g(a, e);
  return {
    record_id: d(t.record_id, `${e}.record_id`),
    zone_id: X(t.zone_id, `${e}.zone_id`),
    timestamp_utc: f(t.timestamp_utc, `${e}.timestamp_utc`),
    activity_type: d(t.activity_type, `${e}.activity_type`),
    reason_code: d(t.reason_code, `${e}.reason_code`),
    severity: d(t.severity, `${e}.severity`),
    explanation: d(t.explanation, `${e}.explanation`)
  };
}
function dt(a) {
  const e = g(a, "activity");
  E(e, "activity");
  const t = d(e.order, "activity.order");
  if (t !== "newest" && t !== "oldest")
    throw new v(
      "activity.order",
      "expected newest or oldest"
    );
  return {
    api_version: b,
    total: y(e.total, "activity.total"),
    offset: y(e.offset, "activity.offset"),
    order: t,
    records: x(e.records, "activity.records").map(
      (i, r) => lt(i, `activity.records[${String(r)}]`)
    )
  };
}
function pt(a, e) {
  const t = g(a, e);
  return {
    ready: w(t.ready, `${e}.ready`),
    qualification_percent: I(
      t.qualification_percent,
      `${e}.qualification_percent`
    ),
    valid_evaluation_percent: I(
      t.valid_evaluation_percent,
      `${e}.valid_evaluation_percent`
    ),
    elapsed_hours: I(t.elapsed_hours, `${e}.elapsed_hours`),
    evaluated_decisions: y(
      t.evaluated_decisions,
      `${e}.evaluated_decisions`
    ),
    valid_evaluations: y(
      t.valid_evaluations,
      `${e}.valid_evaluations`
    ),
    minimum_material_transitions: y(
      t.minimum_material_transitions,
      `${e}.minimum_material_transitions`
    ),
    blocking_reasons: q(
      t.blocking_reasons,
      `${e}.blocking_reasons`
    ),
    blocking_faults: q(
      t.blocking_faults,
      `${e}.blocking_faults`
    )
  };
}
function ut(a) {
  const e = g(a, "shadow");
  return E(e, "shadow"), {
    api_version: b,
    readiness: e.readiness === null ? null : pt(e.readiness, "shadow.readiness"),
    history: x(e.history, "shadow.history").map((t, i) => {
      const r = `shadow.history[${String(i)}]`, n = g(t, r);
      return {
        safety_evaluation_id: d(
          n.safety_evaluation_id,
          `${r}.safety_evaluation_id`
        ),
        evaluated_at_utc: f(
          n.evaluated_at_utc,
          `${r}.evaluated_at_utc`
        ),
        outcome: d(n.outcome, `${r}.outcome`),
        reason_code: d(n.reason_code, `${r}.reason_code`),
        would_command: w(
          n.would_command,
          `${r}.would_command`
        )
      };
    })
  };
}
function ht(a) {
  const e = g(a, "observation");
  if (E(e, "observation"), e.model_ready_history_available !== !1)
    throw new v(
      "observation.model_ready_history_available",
      "Phase 2 must not claim model-ready history"
    );
  return {
    api_version: b,
    collection_active: w(
      e.collection_active,
      "observation.collection_active"
    ),
    observation_revision: y(
      e.observation_revision,
      "observation.observation_revision"
    ),
    calculated_at_utc: f(
      e.calculated_at_utc,
      "observation.calculated_at_utc"
    ),
    usable_temperature_sources: y(
      e.usable_temperature_sources,
      "observation.usable_temperature_sources"
    ),
    degraded_zone_count: y(
      e.degraded_zone_count,
      "observation.degraded_zone_count"
    ),
    presentation_history_hours: y(
      e.presentation_history_hours,
      "observation.presentation_history_hours"
    ),
    model_ready_history_available: !1,
    history_boundary: d(
      e.history_boundary,
      "observation.history_boundary"
    )
  };
}
function mt(a, e) {
  const t = g(a, e);
  return {
    start_utc: f(t.start_utc, `${e}.start_utc`),
    end_utc: f(t.end_utc, `${e}.end_utc`)
  };
}
function gt(a, e) {
  const t = g(a, e), i = t.value;
  if ((typeof i != "string" || i.length === 0) && (typeof i != "number" || !Number.isFinite(i)))
    throw new v(
      `${e}.value`,
      "expected finite number or text"
    );
  return {
    timestamp_utc: f(t.timestamp_utc, `${e}.timestamp_utc`),
    value: i
  };
}
function vt(a, e) {
  const t = g(a, e), i = d(t.value_kind, `${e}.value_kind`);
  if (!nt.has(i))
    throw new v(
      `${e}.value_kind`,
      "unsupported provenance"
    );
  if (i === "predicted" || i === "planned")
    throw new v(
      `${e}.value_kind`,
      "future Phase 3/4 series are not accepted by the Phase 2 panel"
    );
  return {
    kind: d(t.kind, `${e}.kind`),
    value_kind: i,
    unit: X(t.unit, `${e}.unit`),
    source_quality: d(t.source_quality, `${e}.source_quality`),
    coverage_start_utc: f(
      t.coverage_start_utc,
      `${e}.coverage_start_utc`
    ),
    coverage_end_utc: f(
      t.coverage_end_utc,
      `${e}.coverage_end_utc`
    ),
    missing_intervals: x(
      t.missing_intervals,
      `${e}.missing_intervals`
    ).map(
      (r, n) => mt(r, `${e}.missing_intervals[${String(n)}]`)
    ),
    samples: x(t.samples, `${e}.samples`).map(
      (r, n) => gt(r, `${e}.samples[${String(n)}]`)
    )
  };
}
function ft(a, e) {
  const t = g(a, e);
  return {
    annotation_id: d(t.annotation_id, `${e}.annotation_id`),
    timestamp_utc: f(t.timestamp_utc, `${e}.timestamp_utc`),
    reason_code: d(t.reason_code, `${e}.reason_code`),
    activity_record_id: d(
      t.activity_record_id,
      `${e}.activity_record_id`
    )
  };
}
function _t(a) {
  const e = g(a, "timeline");
  if (E(e, "timeline"), e.indoor_prediction_available !== !1)
    throw new v(
      "timeline.indoor_prediction_available",
      "Phase 2 must not claim indoor prediction"
    );
  return {
    api_version: b,
    entry_id: d(e.entry_id, "timeline.entry_id"),
    zone_id: d(e.zone_id, "timeline.zone_id"),
    time_zone: d(e.time_zone, "timeline.time_zone"),
    local_date: d(e.local_date, "timeline.local_date"),
    day_start_utc: f(e.day_start_utc, "timeline.day_start_utc"),
    day_end_utc: f(e.day_end_utc, "timeline.day_end_utc"),
    generated_at_utc: f(
      e.generated_at_utc,
      "timeline.generated_at_utc"
    ),
    indoor_prediction_available: !1,
    capability_statement: d(
      e.capability_statement,
      "timeline.capability_statement"
    ),
    series: x(e.series, "timeline.series").map(
      (t, i) => vt(t, `timeline.series[${String(i)}]`)
    ),
    annotations: x(e.annotations, "timeline.annotations").map(
      (t, i) => ft(t, `timeline.annotations[${String(i)}]`)
    )
  };
}
function yt(a) {
  const e = g(a, "narrative");
  return E(e, "narrative"), {
    api_version: b,
    template_version: y(
      e.template_version,
      "narrative.template_version"
    ),
    entry_id: d(e.entry_id, "narrative.entry_id"),
    zone_id: d(e.zone_id, "narrative.zone_id"),
    control_state: d(e.control_state, "narrative.control_state"),
    reason_code: d(e.reason_code, "narrative.reason_code"),
    temperature_c: N(
      e.temperature_c,
      "narrative.temperature_c"
    ),
    hvac_action: X(e.hvac_action, "narrative.hvac_action"),
    scheduled_target_c: N(
      e.scheduled_target_c,
      "narrative.scheduled_target_c"
    ),
    effective_target_c: N(
      e.effective_target_c,
      "narrative.effective_target_c"
    ),
    next_transition_utc: e.next_transition_utc === null ? null : f(
      e.next_transition_utc,
      "narrative.next_transition_utc"
    ),
    source_degraded: w(
      e.source_degraded,
      "narrative.source_degraded"
    ),
    context_forecast_available: w(
      e.context_forecast_available,
      "narrative.context_forecast_available"
    ),
    included_categories: q(
      e.included_categories,
      "narrative.included_categories"
    ),
    rendered: d(e.rendered, "narrative.rendered")
  };
}
class bt {
  constructor(e, t) {
    if (this.hass = e, this.entryId = t, t.length === 0)
      throw new Error("entryId is required");
  }
  async request(e, t, i = {}) {
    const r = await this.hass.callWS({
      type: e,
      api_version: b,
      entry_id: this.entryId,
      ...i
    });
    return t(r);
  }
  configuration() {
    return this.request(
      "intelligent_climate/config/get",
      ot
    );
  }
  snapshot() {
    return this.request("intelligent_climate/snapshot/get", Se);
  }
  activity(e = 0, t = 100, i = "newest") {
    return this.request("intelligent_climate/activity/list", dt, {
      offset: e,
      limit: t,
      order: i
    });
  }
  shadowStatus() {
    return this.request(
      "intelligent_climate/shadow/status",
      ut
    );
  }
  observationStatus() {
    return this.request(
      "intelligent_climate/observation/status",
      ht
    );
  }
  todayTimeline(e) {
    return this.request(
      "intelligent_climate/timeline/today",
      _t,
      { zone_id: e }
    );
  }
  narrative(e) {
    return this.request(
      "intelligent_climate/narrative/current",
      yt,
      { zone_id: e }
    );
  }
  async dashboardData() {
    const [e, t, i, r, n] = await Promise.all([
      this.configuration(),
      this.snapshot(),
      this.activity(),
      this.shadowStatus(),
      this.observationStatus()
    ]);
    return { configuration: e, snapshot: t, activity: i, shadow: r, observation: n };
  }
  async subscribe(e) {
    return this.hass.connection.subscribeMessage(
      (t) => e(Se(t)),
      {
        type: "intelligent_climate/subscribe",
        api_version: b,
        entry_id: this.entryId
      }
    );
  }
}
const xt = {
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
  fan_action: "Fan-only circulation"
}, $t = {
  off: "Off",
  idle: "Idle",
  heating: "Heating",
  cooling: "Cooling",
  drying: "Drying",
  fan: "Fan only",
  on: "On",
  not_reported: "Not reported",
  unavailable: "Unavailable",
  unknown: "Unknown (older sample)"
}, G = 30, V = 155, wt = V - G, ze = [30, 61.25, 92.5, 123.75, 155];
function re(a) {
  return xt[a] ?? a.replaceAll("_", " ");
}
function Ue(a) {
  return typeof a == "string" ? $t[a] ?? re(a) : String(a);
}
function kt(a) {
  return a.filter(
    (e, t) => t === 0 || a[t - 1]?.value !== e.value
  );
}
function St(a) {
  switch (a) {
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
      return Ue(a);
  }
}
function te(a) {
  return a.samples.filter(
    (e) => typeof e.value == "number"
  );
}
function zt(a, e) {
  if (a.length === 0)
    return "";
  const t = a[0];
  if (t === void 0)
    return "";
  let i = `M ${t.x.toFixed(2)} ${t.y.toFixed(2)}`;
  for (const r of a.slice(1))
    i += e ? ` H ${r.x.toFixed(2)} V ${r.y.toFixed(2)}` : ` L ${r.x.toFixed(2)} ${r.y.toFixed(2)}`;
  return i;
}
const K = class K extends O {
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
    const e = this.timeline, t = this.temperatureRange(e), i = this.renderedSeries(e, t), r = i.find(
      (o) => o.kind === "effective_temperature"
    ), n = r?.sampleCount ?? 0, s = n >= 2, h = e.series.filter(
      (o) => ["hvac_action", "fan_action"].includes(o.kind)
    ), l = this.currentCursor(e);
    return c`
      <div class="legend" aria-label="Timeline legend">
        ${i.map(
      (o) => c`<span class="legend-item">
              <span
                class="swatch ${o.className}"
                aria-hidden="true"
              ></span>
              ${o.label}
              <small>${o.valueKind}</small>
            </span>`
    )}
      </div>
      ${i.length === 0 ? c`<div class="empty" role="status">
              No numeric observations yet.
            </div>` : s ? c`<div class="chart-wrap">
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
                    ${ze.map(
      (o) => c`<line x1="80" x2="970" y1=${o} y2=${o}></line>`
    )}
                    ${[80, 303, 525, 748, 970].map(
      (o) => c`<line
                          x1=${o}
                          x2=${o}
                          y1=${G}
                          y2=${V}
                        ></line>`
    )}
                  </g>
                  <g class="y-axis-labels" aria-hidden="true">
                    ${ze.map((o, u) => {
      const [m, _] = t, $ = _ - (_ - m) * u / 4;
      return c`<text x="72" y=${o + 6} text-anchor="end">
                        ${ae(
        $,
        this.temperatureUnit,
        this.locale
      )}
                      </text>`;
    })}
                  </g>
                  ${i.map(
      (o) => c`<g class="series-group ${o.className}">
                        <path
                          class="series ${o.className}"
                          d=${o.path}
                        ></path>
                        ${o.kind === "effective_temperature" ? o.points.map(
        (u) => c`<circle
                                    class="sample-point measured-temperature"
                                    cx=${u.x}
                                    cy=${u.y}
                                    r="4.5"
                                  ></circle>`
      ) : p}
                      </g>`
    )}
                  ${l === null ? p : c`<line
                          class="now"
                          x1=${l}
                          x2=${l}
                          y1=${G - 5}
                          y2=${V + 5}
                        ></line>`}
                  ${e.annotations.map((o) => {
      const u = this.xPosition(
        Date.parse(o.timestamp_utc),
        e
      );
      return c`<g class="annotation" aria-hidden="true">
                      <circle cx=${u} cy="15" r="6"></circle>
                      <line x1=${u} x2=${u} y1="21" y2=${G + 6}></line>
                    </g>`;
    })}
                  <g class="axis-labels" aria-hidden="true">
                    <text x="80" y="198">12 AM</text>
                    <text x="525" y="198" text-anchor="middle">12 PM</text>
                    <text x="970" y="198" text-anchor="end">12 AM</text>
                  </g>
                </svg>
                ${this.sampleSummary(r)}
              </div>` : c`<div class="empty collecting" role="status">
                <div>
                  <strong>Collecting climate history</strong>
                  <p>
                    ${n} of 2 temperature samples collected. The
                    chart will appear after the next observation.
                  </p>
                  ${this.sampleSummary(r)}
                </div>
              </div>`}
      ${h.length === 0 ? p : c`<div class="state-bands" aria-label="Equipment state timeline">
              ${h.map((o) => this.renderStateSeries(o))}
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
              ${i.map(
      (o) => c`<tr>
                    <th scope="row">${o.label}</th>
                    <td>${o.valueKind}</td>
                    <td>${this.latestValue(o)}</td>
                    <td>${o.coverage}</td>
                    <td>${o.gaps}</td>
                  </tr>`
    )}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }
  renderedSeries(e, t) {
    return e.series.filter(
      (r) => te(r).length > 0 && r.unit !== "%"
    ).map((r) => {
      const n = te(r), s = n.map((l) => ({
        x: this.xPosition(Date.parse(l.timestamp_utc), e),
        y: this.yPosition(l.value, t)
      })), h = n.at(-1);
      if (h === void 0)
        throw new Error("validated timeline series unexpectedly empty");
      return {
        kind: r.kind,
        valueKind: r.value_kind,
        label: re(r.kind),
        className: `${r.value_kind} ${r.kind}`,
        path: zt(s, r.value_kind !== "measured"),
        points: s,
        latest: h.value,
        latestTimestamp: h.timestamp_utc,
        sampleCount: n.length,
        coverage: `${R(
          r.coverage_start_utc,
          this.locale,
          e.time_zone
        )} – ${R(
          r.coverage_end_utc,
          this.locale,
          e.time_zone
        )}`,
        gaps: r.missing_intervals.length
      };
    });
  }
  temperatureRange(e) {
    return this.range(
      e.series.filter((t) => t.unit === "°C").flatMap(
        (t) => te(t).map((i) => i.value)
      )
    );
  }
  sampleSummary(e) {
    return e === void 0 ? p : c`<p class="sample-summary">
      Latest sample
      ${R(
      e.latestTimestamp,
      this.locale,
      this.timeline?.time_zone
    )}
      · Source: effective zone temperature
    </p>`;
  }
  renderStateSeries(e) {
    const t = kt(e.samples);
    return c`<div class="state-row">
        <strong>${re(e.kind)}</strong>
        <div>
          ${t.map(
      (i) => c`<span class="state-chip">
                ${this.stateTimestamp(i)}: ${Ue(i.value)}
              </span>`
    )}
        </div>
      </div>
      ${e.kind === "hvac_action" ? c`<div class="state-row derived">
              <strong>Air handler <small>derived</small></strong>
              <div>
                ${t.map(
      (i) => c`<span class="state-chip">
                      ${this.stateTimestamp(i)}:
                      ${St(i.value)}
                    </span>`
    )}
              </div>
            </div>` : p}`;
  }
  stateTimestamp(e) {
    return R(
      e.timestamp_utc,
      this.locale,
      this.timeline?.time_zone
    );
  }
  range(e) {
    if (e.length === 0)
      return [0, 1];
    const t = Math.min(...e), i = Math.max(...e), r = Math.max((i - t) * 0.15, 0.5);
    return [t - r, i + r];
  }
  xPosition(e, t) {
    const i = Date.parse(t.day_start_utc), r = Date.parse(t.day_end_utc);
    return 80 + (e - i) / (r - i) * 890;
  }
  yPosition(e, t) {
    const [i, r] = t;
    return V - (e - i) / (r - i) * wt;
  }
  currentCursor(e) {
    const t = Date.now();
    return t < Date.parse(e.day_start_utc) || t > Date.parse(e.day_end_utc) ? null : this.xPosition(t, e);
  }
  latestValue(e) {
    return typeof e.latest != "number" ? e.latest : ae(e.latest, this.temperatureUnit, this.locale);
  }
};
K.properties = {
  timeline: { attribute: !1 },
  locale: { type: String },
  temperatureUnit: { type: String, attribute: "temperature-unit" }
}, K.styles = de`
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
      font-size: 24px;
    }
    .y-axis-labels {
      fill: var(--secondary-text-color, #667085);
      font-size: 16px;
    }
    .state-bands {
      display: grid;
      gap: 8px;
      margin-block: 12px;
    }
    .state-row {
      display: grid;
      grid-template-columns: minmax(100px, 150px) 1fr;
      gap: 10px;
      align-items: start;
      font-size: 0.82rem;
    }
    .state-row.derived strong small {
      display: block;
      color: var(--secondary-text-color, #667085);
      font-size: 0.68rem;
      font-weight: 500;
    }
    .state-chip {
      display: inline-block;
      margin: 0 6px 6px 0;
      padding: 4px 8px;
      border: 1px solid var(--divider-color, #d8dde3);
      border-radius: 999px;
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
      .state-row {
        grid-template-columns: 1fr;
      }
    }
  `;
let ne = K;
customElements.get("ic-today-timeline") || customElements.define("ic-today-timeline", ne);
const se = "intelligent-climate.temperature-unit";
function At() {
  try {
    const a = window.localStorage.getItem(se);
    if (a === "fahrenheit" || a === "celsius")
      return a;
  } catch {
  }
  return "home_assistant";
}
function Et(a) {
  try {
    a === "home_assistant" ? window.localStorage.removeItem(se) : window.localStorage.setItem(se, a);
  } catch {
  }
}
function Ct(a, e) {
  return a === "fahrenheit" ? "°F" : a === "celsius" ? "°C" : e;
}
const Ot = de`
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
`, Re = [
  { id: "overview", label: "Overview", icon: "⌂" },
  { id: "sensors", label: "Sensors", icon: "◫" },
  { id: "activity", label: "Activity", icon: "↯" },
  { id: "settings", label: "Settings", icon: "⚙" }
];
function Tt(a) {
  return Re.some((e) => e.id === a);
}
const J = class J extends O {
  constructor() {
    super(...arguments), this.narrow = !1, this.activeRoute = "overview", this.selectedEntryId = "", this.selectedZoneId = "", this.loading = !0, this.errorMessage = "", this.activityFilter = "all", this.temperatureUnitPreference = At(), this.activityLoadingOlder = !1, this.loadGeneration = 0, this.detailLoadGeneration = 0, this.entryChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLSelectElement && (this.selectedEntryId = t.value, this.loadEntry(t.value));
    }, this.filterChanged = (e) => {
      const t = e.currentTarget;
      t instanceof HTMLSelectElement && (this.activityFilter = t.value);
    }, this.temperatureUnitChanged = (e) => {
      const t = e.currentTarget;
      if (!(t instanceof HTMLSelectElement))
        return;
      const i = t.value;
      i !== "home_assistant" && i !== "fahrenheit" && i !== "celsius" || (this.temperatureUnitPreference = i, Et(i));
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
        const r = new Set(
          e.activity.records.map((s) => s.record_id)
        ), n = [
          ...e.activity.records,
          ...i.records.filter((s) => !r.has(s.record_id))
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
    };
  }
  disconnectedCallback() {
    this.loadGeneration += 1, this.detailLoadGeneration += 1, this.unsubscribe?.(), this.unsubscribe = void 0, super.disconnectedCallback();
  }
  willUpdate(e) {
    if (e.has("route")) {
      const t = this.route?.path?.split("/").find(Boolean);
      t !== void 0 && Tt(t) && (this.activeRoute = t);
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
          ${Re.map(
      (t) => c`<button
                type="button"
                class=${this.activeRoute === t.id ? "active" : ""}
                aria-current=${this.activeRoute === t.id ? "page" : p}
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
      case "sensors":
        return this.renderSensors();
      case "activity":
        return this.renderActivity();
      case "settings":
        return this.renderSettings();
    }
  }
  renderOverview() {
    const e = this.requireData(), t = rt(e.snapshot.control_state), i = e.shadow.readiness, r = this.selectedZone();
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
              >${e.snapshot.reason_code === null ? "No current alert" : j(e.snapshot.reason_code)}</span
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
            ><strong>${r?.name ?? "Unavailable"}</strong>
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
              >${this.selectedZone()?.humidity_sources.some((n) => n.enabled) === !0 ? "Measured" : "Not configured"}</strong
            >
          </div>
          <b
            >${this.humidity(this.selectedZoneSnapshot()?.effective_humidity_pct ?? null, this.selectedZone()?.humidity_sources.some((n) => n.enabled) === !0)}</b
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
              ${i?.ready === !0 ? "✓ Ready" : "◌ Observing"}
            </span>
          </div>
          ${i === null ? c`<p class="muted">
                  Shadow qualification has not started. Observe Only remains
                  fully available.
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
                      <dd>${i.valid_evaluation_percent.toFixed(0)}%</dd>
                    </div>
                    <div>
                      <dt>Transitions</dt>
                      <dd>${i.minimum_material_transitions} / 2</dd>
                    </div>
                  </dl>
                  ${i.blocking_reasons.length === 0 ? p : c`<p class="blocking">
                          <strong>Still needed:</strong>
                          ${i.blocking_reasons.map((n) => n.replaceAll("_", " ")).join(", ")}
                        </p>`}
                  ${i.blocking_faults.length === 0 ? p : c`<p class="fault">
                          <strong>Blocking fault:</strong>
                          ${i.blocking_faults.join(", ")}
                        </p>`}`}
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
    return e.length < 2 ? p : c`<div
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
      ), r = i?.sensor_data_degraded === !0 || i?.thermostat_data_degraded === !0;
      return c`<article class="card zone-health-card">
            <div class="card-heading">
              <div>
                <span class="eyebrow">Zone</span>
                <h3>${t.name}</h3>
              </div>
              <span class="health-pill ${r ? "warning" : "healthy"}"
                >${r ? "⚠ Review" : "✓ Healthy"}</span
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
            ${i?.sensor_data_degraded === !0 ? c`<p class="warning-copy">Temperature source data is degraded.</p>` : p}
            ${i?.thermostat_data_degraded === !0 ? c`<p class="warning-copy">Thermostat observation data is degraded.</p>` : p}
            ${this.enabledSourceCount(t.humidity_sources) === 0 ? c`<p class="muted">Humidity is not configured for this zone. Reconfigure the zone to select a humidity sensor or thermostat.</p>` : p}
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
              </button>` : p}
      </section>
    `;
  }
  renderActivityRecords(e) {
    return e.length === 0 ? c`<div class="empty-state" role="status">
        No matching material activity is available.
      </div>` : c`<ol class="activity-list">
      ${e.map((t) => {
      const i = this.data?.configuration.zones.find(
        (r) => r.zone_id === t.zone_id
      );
      return c`<li>
          <span
            class="activity-marker severity-${t.severity}"
            aria-hidden="true"
          ></span>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${j(t.activity_type)}</strong
              ><time datetime=${t.timestamp_utc}
                >${this.time(t.timestamp_utc)}</time
              >
            </div>
            <p>${t.explanation}</p>
            <div class="activity-meta">
              <span>${j(t.reason_code)}</span
              >${i === void 0 ? p : c`<span>${i.name}</span>`}<span>${t.severity}</span>${this.repairRecordStatus(t)}
            </div>
          </div>
        </li>`;
    })}
    </ol>`;
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
          <a href="/developer-tools/yaml"
            ><span aria-hidden="true">⇩</span>
            <div>
              <strong>Diagnostics</strong
              ><small>Download from the integration device page</small>
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
    return Ct(
      this.temperatureUnitPreference,
      this.hass.config.unit_system.temperature
    );
  }
  temperature(e) {
    return ae(e, this.temperatureUnit(), this.locale());
  }
  humidity(e, t = !0) {
    return t ? e === null ? "Unavailable" : `${new Intl.NumberFormat(this.locale(), { maximumFractionDigits: 1 }).format(e)}%` : "Not configured";
  }
  time(e) {
    return R(e, this.locale(), this.timeline?.time_zone);
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
      }[e.control_state] ?? `Current status: ${j(e.control_state)}.`
    ], r = e.effective_target_c ?? e.scheduled_target_c;
    if (r !== null) {
      const n = e.next_transition_utc === null ? "" : ` until ${this.time(e.next_transition_utc)}`;
      i.push(
        `The current target is ${this.temperature(r)}${n}.`
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
      return p;
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
    this.unsubscribe?.(), this.unsubscribe = void 0, this.loading = !0, this.errorMessage = "", this.data = void 0, this.timeline = void 0, this.narrative = void 0;
    const i = new bt(this.hass, e);
    this.client = i;
    try {
      const r = await i.dashboardData();
      if (t !== this.loadGeneration)
        return;
      this.data = r;
      const n = r.configuration.zones[0];
      if (this.selectedZoneId = n?.zone_id ?? "", this.selectedZoneId.length > 0 && await this.loadZoneDetails(t), t !== this.loadGeneration)
        return;
      this.unsubscribe = await i.subscribe((s) => {
        this.applySnapshot(s);
      });
    } catch (r) {
      if (t !== this.loadGeneration)
        return;
      this.errorMessage = this.describeError(r);
    } finally {
      t === this.loadGeneration && (this.loading = !1);
    }
  }
  async loadZoneDetails(e) {
    if (this.client === void 0 || this.selectedZoneId.length === 0)
      return;
    const t = ++this.detailLoadGeneration, [i, r] = await Promise.allSettled([
      this.client.todayTimeline(this.selectedZoneId),
      this.client.narrative(this.selectedZoneId)
    ]);
    e !== this.loadGeneration || t !== this.detailLoadGeneration || (this.timeline = i.status === "fulfilled" ? i.value : void 0, this.narrative = r.status === "fulfilled" ? r.value : void 0);
  }
  applySnapshot(e) {
    this.data === void 0 || e.entry_id !== this.selectedEntryId || (this.data = { ...this.data, snapshot: e }, this.loadZoneDetails(this.loadGeneration));
  }
  describeError(e) {
    return e instanceof v ? `The backend returned data this frontend cannot safely display (${e.message}). Reload the integration or update the candidate.` : e instanceof Error ? e.message : "An unknown local data error occurred.";
  }
  navigate(e) {
    this.activeRoute = e, window.history.replaceState(null, "", `/intelligent-climate/${e}`), this.shadowRoot?.querySelector("#main-content")?.focus();
  }
  selectZone(e) {
    this.selectedZoneId = e, this.loadZoneDetails(this.loadGeneration);
  }
};
J.properties = {
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
  activityLoadingOlder: { state: !0 }
}, J.styles = [
  Ot,
  de`
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
let oe = J;
customElements.get("intelligent-climate-panel") || customElements.define("intelligent-climate-panel", oe);
