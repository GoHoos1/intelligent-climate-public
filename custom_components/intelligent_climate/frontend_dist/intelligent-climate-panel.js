const Y = globalThis, ge = Y.ShadowRoot && (Y.ShadyCSS === void 0 || Y.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, ve = /* @__PURE__ */ Symbol(), ye = /* @__PURE__ */ new WeakMap();
let Ue = class {
  constructor(e, t, i) {
    if (this._$cssResult$ = !0, i !== ve) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = e, this.t = t;
  }
  get styleSheet() {
    let e = this.o;
    const t = this.t;
    if (ge && e === void 0) {
      const i = t !== void 0 && t.length === 1;
      i && (e = ye.get(t)), e === void 0 && ((this.o = e = new CSSStyleSheet()).replaceSync(this.cssText), i && ye.set(t, e));
    }
    return e;
  }
  toString() {
    return this.cssText;
  }
};
const Ke = (r) => new Ue(typeof r == "string" ? r : r + "", void 0, ve), ie = (r, ...e) => {
  const t = r.length === 1 ? r[0] : e.reduce((i, a, n) => i + ((s) => {
    if (s._$cssResult$ === !0) return s.cssText;
    if (typeof s == "number") return s;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + s + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(a) + r[n + 1], r[0]);
  return new Ue(t, r, ve);
}, Qe = (r, e) => {
  if (ge) r.adoptedStyleSheets = e.map((t) => t instanceof CSSStyleSheet ? t : t.styleSheet);
  else for (const t of e) {
    const i = document.createElement("style"), a = Y.litNonce;
    a !== void 0 && i.setAttribute("nonce", a), i.textContent = t.cssText, r.appendChild(i);
  }
}, $e = ge ? (r) => r : (r) => r instanceof CSSStyleSheet ? ((e) => {
  let t = "";
  for (const i of e.cssRules) t += i.cssText;
  return Ke(t);
})(r) : r;
const { is: Je, defineProperty: Xe, getOwnPropertyDescriptor: et, getOwnPropertyNames: tt, getOwnPropertySymbols: it, getPrototypeOf: rt } = Object, re = globalThis, xe = re.trustedTypes, at = xe ? xe.emptyScript : "", nt = re.reactiveElementPolyfillSupport, q = (r, e) => r, oe = { toAttribute(r, e) {
  switch (e) {
    case Boolean:
      r = r ? at : null;
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
} }, Oe = (r, e) => !Je(r, e), we = { attribute: !0, type: String, converter: oe, reflect: !1, useDefault: !1, hasChanged: Oe };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), re.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
let M = class extends HTMLElement {
  static addInitializer(e) {
    this._$Ei(), (this.l ??= []).push(e);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(e, t = we) {
    if (t.state && (t.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(e) && ((t = Object.create(t)).wrapped = !0), this.elementProperties.set(e, t), !t.noAccessor) {
      const i = /* @__PURE__ */ Symbol(), a = this.getPropertyDescriptor(e, i, t);
      a !== void 0 && Xe(this.prototype, e, a);
    }
  }
  static getPropertyDescriptor(e, t, i) {
    const { get: a, set: n } = et(this.prototype, e) ?? { get() {
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
    return this.elementProperties.get(e) ?? we;
  }
  static _$Ei() {
    if (this.hasOwnProperty(q("elementProperties"))) return;
    const e = rt(this);
    e.finalize(), e.l !== void 0 && (this.l = [...e.l]), this.elementProperties = new Map(e.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(q("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(q("properties"))) {
      const t = this.properties, i = [...tt(t), ...it(t)];
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
      for (const a of i) t.unshift($e(a));
    } else e !== void 0 && t.push($e(e));
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
    return Qe(e, this.constructor.elementStyles), e;
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
      const n = (i.converter?.toAttribute !== void 0 ? i.converter : oe).toAttribute(t, i.type);
      this._$Em = e, n == null ? this.removeAttribute(a) : this.setAttribute(a, n), this._$Em = null;
    }
  }
  _$AK(e, t) {
    const i = this.constructor, a = i._$Eh.get(e);
    if (a !== void 0 && this._$Em !== a) {
      const n = i.getPropertyOptions(a), s = typeof n.converter == "function" ? { fromAttribute: n.converter } : n.converter?.fromAttribute !== void 0 ? n.converter : oe;
      this._$Em = a;
      const l = s.fromAttribute(t, n.type);
      this[a] = l ?? this._$Ej?.get(a) ?? l, this._$Em = null;
    }
  }
  requestUpdate(e, t, i, a = !1, n) {
    if (e !== void 0) {
      const s = this.constructor;
      if (a === !1 && (n = this[e]), i ??= s.getPropertyOptions(e), !((i.hasChanged ?? Oe)(n, t) || i.useDefault && i.reflect && n === this._$Ej?.get(e) && !this.hasAttribute(s._$Eu(e, i)))) return;
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
M.elementStyles = [], M.shadowRootOptions = { mode: "open" }, M[q("elementProperties")] = /* @__PURE__ */ new Map(), M[q("finalized")] = /* @__PURE__ */ new Map(), nt?.({ ReactiveElement: M }), (re.reactiveElementVersions ??= []).push("2.1.2");
const fe = globalThis, ke = (r) => r, J = fe.trustedTypes, Se = J ? J.createPolicy("lit-html", { createHTML: (r) => r }) : void 0, Ne = "$lit$", z = `lit$${Math.random().toFixed(9).slice(2)}$`, Re = "?" + z, st = `<${Re}>`, I = document, Z = () => I.createComment(""), F = (r) => r === null || typeof r != "object" && typeof r != "function", _e = Array.isArray, ot = (r) => _e(r) || typeof r?.[Symbol.iterator] == "function", se = `[ 	
\f\r]`, R = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, ze = /-->/g, Ae = />/g, E = RegExp(`>|${se}(?:([^\\s"'>=/]+)(${se}*=${se}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), Ee = /'/g, Ce = /"/g, Le = /^(?:script|style|textarea|title)$/i, He = (r) => (e, ...t) => ({ _$litType$: r, strings: e, values: t }), o = He(1), C = He(2), O = /* @__PURE__ */ Symbol.for("lit-noChange"), h = /* @__PURE__ */ Symbol.for("lit-nothing"), Te = /* @__PURE__ */ new WeakMap(), D = I.createTreeWalker(I, 129);
function qe(r, e) {
  if (!_e(r) || !r.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return Se !== void 0 ? Se.createHTML(e) : e;
}
const lt = (r, e) => {
  const t = r.length - 1, i = [];
  let a, n = e === 2 ? "<svg>" : e === 3 ? "<math>" : "", s = R;
  for (let l = 0; l < t; l++) {
    const c = r[l];
    let p, g, d = -1, v = 0;
    for (; v < c.length && (s.lastIndex = v, g = s.exec(c), g !== null); ) v = s.lastIndex, s === R ? g[1] === "!--" ? s = ze : g[1] !== void 0 ? s = Ae : g[2] !== void 0 ? (Le.test(g[2]) && (a = RegExp("</" + g[2], "g")), s = E) : g[3] !== void 0 && (s = E) : s === E ? g[0] === ">" ? (s = a ?? R, d = -1) : g[1] === void 0 ? d = -2 : (d = s.lastIndex - g[2].length, p = g[1], s = g[3] === void 0 ? E : g[3] === '"' ? Ce : Ee) : s === Ce || s === Ee ? s = E : s === ze || s === Ae ? s = R : (s = E, a = void 0);
    const b = s === E && r[l + 1].startsWith("/>") ? " " : "";
    n += s === R ? c + st : d >= 0 ? (i.push(p), c.slice(0, d) + Ne + c.slice(d) + z + b) : c + z + (d === -2 ? l : b);
  }
  return [qe(r, n + (r[t] || "<?>") + (e === 2 ? "</svg>" : e === 3 ? "</math>" : "")), i];
};
class j {
  constructor({ strings: e, _$litType$: t }, i) {
    let a;
    this.parts = [];
    let n = 0, s = 0;
    const l = e.length - 1, c = this.parts, [p, g] = lt(e, t);
    if (this.el = j.createElement(p, i), D.currentNode = this.el.content, t === 2 || t === 3) {
      const d = this.el.content.firstChild;
      d.replaceWith(...d.childNodes);
    }
    for (; (a = D.nextNode()) !== null && c.length < l; ) {
      if (a.nodeType === 1) {
        if (a.hasAttributes()) for (const d of a.getAttributeNames()) if (d.endsWith(Ne)) {
          const v = g[s++], b = a.getAttribute(d).split(z), S = /([.?@])?(.*)/.exec(v);
          c.push({ type: 1, index: n, name: S[2], strings: b, ctor: S[1] === "." ? dt : S[1] === "?" ? ut : S[1] === "@" ? pt : ae }), a.removeAttribute(d);
        } else d.startsWith(z) && (c.push({ type: 6, index: n }), a.removeAttribute(d));
        if (Le.test(a.tagName)) {
          const d = a.textContent.split(z), v = d.length - 1;
          if (v > 0) {
            a.textContent = J ? J.emptyScript : "";
            for (let b = 0; b < v; b++) a.append(d[b], Z()), D.nextNode(), c.push({ type: 2, index: ++n });
            a.append(d[v], Z());
          }
        }
      } else if (a.nodeType === 8) if (a.data === Re) c.push({ type: 2, index: n });
      else {
        let d = -1;
        for (; (d = a.data.indexOf(z, d + 1)) !== -1; ) c.push({ type: 7, index: n }), d += z.length - 1;
      }
      n++;
    }
  }
  static createElement(e, t) {
    const i = I.createElement("template");
    return i.innerHTML = e, i;
  }
}
function N(r, e, t = r, i) {
  if (e === O) return e;
  let a = i !== void 0 ? t._$Co?.[i] : t._$Cl;
  const n = F(e) ? void 0 : e._$litDirective$;
  return a?.constructor !== n && (a?._$AO?.(!1), n === void 0 ? a = void 0 : (a = new n(r), a._$AT(r, t, i)), i !== void 0 ? (t._$Co ??= [])[i] = a : t._$Cl = a), a !== void 0 && (e = N(r, a._$AS(r, e.values), a, i)), e;
}
class ct {
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
    const { el: { content: t }, parts: i } = this._$AD, a = (e?.creationScope ?? I).importNode(t, !0);
    D.currentNode = a;
    let n = D.nextNode(), s = 0, l = 0, c = i[0];
    for (; c !== void 0; ) {
      if (s === c.index) {
        let p;
        c.type === 2 ? p = new B(n, n.nextSibling, this, e) : c.type === 1 ? p = new c.ctor(n, c.name, c.strings, this, e) : c.type === 6 && (p = new ht(n, this, e)), this._$AV.push(p), c = i[++l];
      }
      s !== c?.index && (n = D.nextNode(), s++);
    }
    return D.currentNode = I, a;
  }
  p(e) {
    let t = 0;
    for (const i of this._$AV) i !== void 0 && (i.strings !== void 0 ? (i._$AI(e, i, t), t += i.strings.length - 2) : i._$AI(e[t])), t++;
  }
}
class B {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(e, t, i, a) {
    this.type = 2, this._$AH = h, this._$AN = void 0, this._$AA = e, this._$AB = t, this._$AM = i, this.options = a, this._$Cv = a?.isConnected ?? !0;
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
    e = N(this, e, t), F(e) ? e === h || e == null || e === "" ? (this._$AH !== h && this._$AR(), this._$AH = h) : e !== this._$AH && e !== O && this._(e) : e._$litType$ !== void 0 ? this.$(e) : e.nodeType !== void 0 ? this.T(e) : ot(e) ? this.k(e) : this._(e);
  }
  O(e) {
    return this._$AA.parentNode.insertBefore(e, this._$AB);
  }
  T(e) {
    this._$AH !== e && (this._$AR(), this._$AH = this.O(e));
  }
  _(e) {
    this._$AH !== h && F(this._$AH) ? this._$AA.nextSibling.data = e : this.T(I.createTextNode(e)), this._$AH = e;
  }
  $(e) {
    const { values: t, _$litType$: i } = e, a = typeof i == "number" ? this._$AC(e) : (i.el === void 0 && (i.el = j.createElement(qe(i.h, i.h[0]), this.options)), i);
    if (this._$AH?._$AD === a) this._$AH.p(t);
    else {
      const n = new ct(a, this), s = n.u(this.options);
      n.p(t), this.T(s), this._$AH = n;
    }
  }
  _$AC(e) {
    let t = Te.get(e.strings);
    return t === void 0 && Te.set(e.strings, t = new j(e)), t;
  }
  k(e) {
    _e(this._$AH) || (this._$AH = [], this._$AR());
    const t = this._$AH;
    let i, a = 0;
    for (const n of e) a === t.length ? t.push(i = new B(this.O(Z()), this.O(Z()), this, this.options)) : i = t[a], i._$AI(n), a++;
    a < t.length && (this._$AR(i && i._$AB.nextSibling, a), t.length = a);
  }
  _$AR(e = this._$AA.nextSibling, t) {
    for (this._$AP?.(!1, !0, t); e !== this._$AB; ) {
      const i = ke(e).nextSibling;
      ke(e).remove(), e = i;
    }
  }
  setConnected(e) {
    this._$AM === void 0 && (this._$Cv = e, this._$AP?.(e));
  }
}
class ae {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(e, t, i, a, n) {
    this.type = 1, this._$AH = h, this._$AN = void 0, this.element = e, this.name = t, this._$AM = a, this.options = n, i.length > 2 || i[0] !== "" || i[1] !== "" ? (this._$AH = Array(i.length - 1).fill(new String()), this.strings = i) : this._$AH = h;
  }
  _$AI(e, t = this, i, a) {
    const n = this.strings;
    let s = !1;
    if (n === void 0) e = N(this, e, t, 0), s = !F(e) || e !== this._$AH && e !== O, s && (this._$AH = e);
    else {
      const l = e;
      let c, p;
      for (e = n[0], c = 0; c < n.length - 1; c++) p = N(this, l[i + c], t, c), p === O && (p = this._$AH[c]), s ||= !F(p) || p !== this._$AH[c], p === h ? e = h : e !== h && (e += (p ?? "") + n[c + 1]), this._$AH[c] = p;
    }
    s && !a && this.j(e);
  }
  j(e) {
    e === h ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, e ?? "");
  }
}
class dt extends ae {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(e) {
    this.element[this.name] = e === h ? void 0 : e;
  }
}
class ut extends ae {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(e) {
    this.element.toggleAttribute(this.name, !!e && e !== h);
  }
}
class pt extends ae {
  constructor(e, t, i, a, n) {
    super(e, t, i, a, n), this.type = 5;
  }
  _$AI(e, t = this) {
    if ((e = N(this, e, t, 0) ?? h) === O) return;
    const i = this._$AH, a = e === h && i !== h || e.capture !== i.capture || e.once !== i.once || e.passive !== i.passive, n = e !== h && (i === h || a);
    a && this.element.removeEventListener(this.name, this, i), n && this.element.addEventListener(this.name, this, e), this._$AH = e;
  }
  handleEvent(e) {
    typeof this._$AH == "function" ? this._$AH.call(this.options?.host ?? this.element, e) : this._$AH.handleEvent(e);
  }
}
class ht {
  constructor(e, t, i) {
    this.element = e, this.type = 6, this._$AN = void 0, this._$AM = t, this.options = i;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(e) {
    N(this, e);
  }
}
const mt = fe.litHtmlPolyfillSupport;
mt?.(j, B), (fe.litHtmlVersions ??= []).push("3.3.3");
const gt = (r, e, t) => {
  const i = t?.renderBefore ?? e;
  let a = i._$litPart$;
  if (a === void 0) {
    const n = t?.renderBefore ?? null;
    i._$litPart$ = a = new B(e.insertBefore(Z(), n), n, void 0, t ?? {});
  }
  return a._$AI(r), a;
};
const be = globalThis;
class P extends M {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const e = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= e.firstChild, e;
  }
  update(e) {
    const t = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(e), this._$Do = gt(t, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(!0);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(!1);
  }
  render() {
    return O;
  }
}
P._$litElement$ = !0, P.finalized = !0, be.litElementHydrateSupport?.({ LitElement: P });
const vt = be.litElementPolyfillSupport;
vt?.({ LitElement: P });
(be.litElementVersions ??= []).push("4.2.2");
const ft = {
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
function _t(r) {
  return ft[r] ?? {
    label: r.replaceAll("_", " "),
    icon: "●",
    tone: "neutral",
    automationOff: !1
  };
}
function le(r, e, t) {
  if (r === null)
    return "Unavailable";
  const i = e === "°F" ? r * 9 / 5 + 32 : r;
  return `${new Intl.NumberFormat(t, { maximumFractionDigits: 1 }).format(i)}${e}`;
}
function H(r, e, t) {
  return new Intl.DateTimeFormat(e, {
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    day: "numeric",
    ...t === void 0 ? {} : { timeZone: t }
  }).format(new Date(r));
}
function V(r) {
  return r.split("_").filter((e) => e.length > 0).map((e) => e.charAt(0).toUpperCase() + e.slice(1)).join(" ");
}
const $ = 1, bt = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
], yt = /* @__PURE__ */ new Set([
  "none",
  "home",
  "away",
  "sleep",
  "vacation",
  "guest",
  "custom"
]);
class f extends Error {
  constructor(e, t) {
    super(`${e}: ${t}`), this.name = "FrontendContractError";
  }
}
const $t = /* @__PURE__ */ new Set([
  "measured",
  "configured",
  "calculated",
  "forecast",
  "predicted",
  "planned"
]);
function m(r, e) {
  if (typeof r != "object" || r === null || Array.isArray(r))
    throw new f(e, "expected object");
  return r;
}
function x(r, e) {
  if (!Array.isArray(r))
    throw new f(e, "expected array");
  return r;
}
function u(r, e) {
  if (typeof r != "string" || r.length === 0)
    throw new f(e, "expected non-empty string");
  return r;
}
function ne(r, e) {
  return r === null ? null : u(r, e);
}
function w(r, e) {
  if (typeof r != "boolean")
    throw new f(e, "expected boolean");
  return r;
}
function U(r, e) {
  if (typeof r != "number" || !Number.isFinite(r))
    throw new f(e, "expected finite number");
  return r;
}
function y(r, e) {
  const t = U(r, e);
  if (!Number.isInteger(t) || t < 0)
    throw new f(e, "expected non-negative integer");
  return t;
}
function A(r, e) {
  return r === null ? null : U(r, e);
}
function _(r, e) {
  const t = u(r, e);
  if (!Number.isFinite(Date.parse(t)))
    throw new f(e, "expected ISO timestamp");
  return t;
}
function Ze(r, e) {
  const t = u(r, e);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t))
    throw new f(e, "expected YYYY-MM-DD local date");
  return t;
}
function Fe(r, e) {
  const t = u(r, e);
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(t))
    throw new f(e, "expected HH:MM local time");
  return t;
}
function k(r, e) {
  if (r.api_version !== $)
    throw new f(
      `${e}.api_version`,
      `expected ${String($)}`
    );
}
function G(r, e) {
  return x(r, e).map(
    (t, i) => u(t, `${e}[${String(i)}]`)
  );
}
function ce(r, e) {
  const t = m(r, e), i = u(t.kind, `${e}.kind`);
  if (i !== "single" && i !== "range")
    throw new f(`${e}.kind`, "expected single or range");
  return {
    kind: i,
    target_c: A(t.target_c, `${e}.target_c`),
    heat_target_c: A(
      t.heat_target_c,
      `${e}.heat_target_c`
    ),
    cool_target_c: A(
      t.cool_target_c,
      `${e}.cool_target_c`
    )
  };
}
function xt(r, e) {
  const t = m(r, e), i = u(t.occupancy_label, `${e}.occupancy_label`);
  if (!yt.has(i))
    throw new f(
      `${e}.occupancy_label`,
      "unsupported occupancy label"
    );
  return {
    period_id: u(t.period_id, `${e}.period_id`),
    local_start: Fe(t.local_start, `${e}.local_start`),
    label: typeof t.label == "string" ? t.label : u(t.label, `${e}.label`),
    occupancy_label: i,
    target: ce(t.target, `${e}.target`),
    tolerance_c: U(t.tolerance_c, `${e}.tolerance_c`)
  };
}
function wt(r, e) {
  const t = m(r, e), i = m(t.days, `${e}.days`), a = Object.fromEntries(
    bt.map((n) => [
      n,
      x(i[n], `${e}.days.${n}`).map(
        (s, l) => xt(s, `${e}.days.${n}[${String(l)}]`)
      )
    ])
  );
  return {
    profile_id: u(t.profile_id, `${e}.profile_id`),
    name: u(t.name, `${e}.name`),
    enabled: w(t.enabled, `${e}.enabled`),
    days: a
  };
}
function je(r, e) {
  const t = m(r, e);
  if (t.schedule_schema_version !== 1)
    throw new f(
      `${e}.schedule_schema_version`,
      "expected 1"
    );
  const i = m(t.zones, `${e}.zones`), a = {};
  for (const [n, s] of Object.entries(i)) {
    const l = `${e}.zones.${n}`, c = m(s, l);
    a[n] = {
      zone_id: u(c.zone_id, `${l}.zone_id`),
      enabled: w(c.enabled, `${l}.enabled`),
      selected_profile_id: u(
        c.selected_profile_id,
        `${l}.selected_profile_id`
      ),
      profiles: x(c.profiles, `${l}.profiles`).map(
        (p, g) => wt(p, `${l}.profiles[${String(g)}]`)
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
    revision: y(t.revision, `${e}.revision`),
    zones: a,
    saved_at_utc: _(t.saved_at_utc, `${e}.saved_at_utc`)
  };
}
function kt(r) {
  const e = m(r, "schedule");
  return k(e, "schedule"), {
    api_version: $,
    revision: y(e.revision, "schedule.revision"),
    schedule: e.schedule === null ? null : je(e.schedule, "schedule.schedule")
  };
}
function St(r) {
  const e = m(r, "schedule_validation");
  if (k(e, "schedule_validation"), e.valid !== !0)
    throw new f(
      "schedule_validation.valid",
      "expected true"
    );
  return {
    api_version: $,
    valid: !0,
    revision: y(
      e.revision,
      "schedule_validation.revision"
    )
  };
}
function zt(r, e) {
  const t = m(r, e);
  return {
    zone_id: u(t.zone_id, `${e}.zone_id`),
    profile_id: u(t.profile_id, `${e}.profile_id`),
    period_id: u(t.period_id, `${e}.period_id`),
    target: ce(t.target, `${e}.target`),
    next_target: t.next_target === null ? null : ce(t.next_target, `${e}.next_target`),
    next_boundary_utc: _(
      t.next_boundary_utc,
      `${e}.next_boundary_utc`
    ),
    next_material_transition_utc: t.next_material_transition_utc === null ? null : _(
      t.next_material_transition_utc,
      `${e}.next_material_transition_utc`
    ),
    inherited_from_previous_day: w(
      t.inherited_from_previous_day,
      `${e}.inherited_from_previous_day`
    )
  };
}
function At(r, e) {
  const t = m(r, e), i = u(t.kind, `${e}.kind`);
  if (i !== "gap" && i !== "fold")
    throw new f(`${e}.kind`, "expected gap or fold");
  return {
    zone_id: u(t.zone_id, `${e}.zone_id`),
    profile_id: u(t.profile_id, `${e}.profile_id`),
    period_id: u(t.period_id, `${e}.period_id`),
    local_date: Ze(t.local_date, `${e}.local_date`),
    local_start: Fe(t.local_start, `${e}.local_start`),
    kind: i,
    occurs_at_utc: _(t.occurs_at_utc, `${e}.occurs_at_utc`),
    explanation: u(t.explanation, `${e}.explanation`)
  };
}
function Et(r) {
  const e = m(r, "schedule_preview");
  if (k(e, "schedule_preview"), e.authoritative !== !1)
    throw new f(
      "schedule_preview.authoritative",
      "preview must be nonauthoritative"
    );
  return {
    api_version: $,
    authoritative: !1,
    at_utc: _(e.at_utc, "schedule_preview.at_utc"),
    time_zone: u(e.time_zone, "schedule_preview.time_zone"),
    preview_week_start_local: Ze(
      e.preview_week_start_local,
      "schedule_preview.preview_week_start_local"
    ),
    zones: x(e.zones, "schedule_preview.zones").map(
      (t, i) => zt(t, `schedule_preview.zones[${String(i)}]`)
    ),
    dst_warnings: x(
      e.dst_warnings,
      "schedule_preview.dst_warnings"
    ).map(
      (t, i) => At(t, `schedule_preview.dst_warnings[${String(i)}]`)
    )
  };
}
function Ct(r) {
  const e = m(r, "schedule_save");
  return k(e, "schedule_save"), {
    api_version: $,
    revision: y(e.revision, "schedule_save.revision"),
    schedule: je(e.schedule, "schedule_save.schedule")
  };
}
function Tt(r, e) {
  const t = m(r, e), i = (n, s) => x(n, s).map((l, c) => {
    const p = `${s}[${String(c)}]`, g = m(l, p);
    return {
      entity_id: u(g.entity_id, `${p}.entity_id`),
      enabled: w(g.enabled, `${p}.enabled`)
    };
  }), a = (n, s) => x(n, s).map((l, c) => {
    const p = `${s}[${String(c)}]`, g = m(l, p);
    return {
      entity_id: u(g.entity_id, `${p}.entity_id`),
      enabled: w(g.enabled, `${p}.enabled`),
      reviewed: w(g.reviewed, `${p}.reviewed`)
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
    stage_entity_ids: G(
      t.stage_entity_ids,
      `${e}.stage_entity_ids`
    ),
    fan_entity_ids: a(t.fan_entity_ids, `${e}.fan_entity_ids`)
  };
}
function Dt(r) {
  const e = m(r, "config");
  return k(e, "config"), {
    api_version: $,
    config: m(e.config, "config.config"),
    options: m(e.options, "config.options"),
    active_repairs: G(e.active_repairs, "config.active_repairs"),
    zones: x(e.zones, "config.zones").map(
      (t, i) => Tt(t, `config.zones[${String(i)}]`)
    )
  };
}
function Pt(r, e) {
  const t = m(r, e);
  return {
    zone_id: u(t.zone_id, `${e}.zone_id`),
    effective_temperature_c: A(
      t.effective_temperature_c,
      `${e}.effective_temperature_c`
    ),
    effective_humidity_pct: A(
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
function De(r) {
  const e = m(r, "snapshot");
  return k(e, "snapshot"), {
    api_version: $,
    entry_id: u(e.entry_id, "snapshot.entry_id"),
    observation_revision: y(
      e.observation_revision,
      "snapshot.observation_revision"
    ),
    calculated_at_utc: _(
      e.calculated_at_utc,
      "snapshot.calculated_at_utc"
    ),
    control_state: u(e.control_state, "snapshot.control_state"),
    reason_code: ne(e.reason_code, "snapshot.reason_code"),
    zones: x(e.zones, "snapshot.zones").map(
      (t, i) => Pt(t, `snapshot.zones[${String(i)}]`)
    )
  };
}
function It(r, e) {
  const t = m(r, e);
  return {
    record_id: u(t.record_id, `${e}.record_id`),
    zone_id: ne(t.zone_id, `${e}.zone_id`),
    timestamp_utc: _(t.timestamp_utc, `${e}.timestamp_utc`),
    activity_type: u(t.activity_type, `${e}.activity_type`),
    reason_code: u(t.reason_code, `${e}.reason_code`),
    severity: u(t.severity, `${e}.severity`),
    explanation: u(t.explanation, `${e}.explanation`)
  };
}
function Mt(r) {
  const e = m(r, "activity");
  k(e, "activity");
  const t = u(e.order, "activity.order");
  if (t !== "newest" && t !== "oldest")
    throw new f(
      "activity.order",
      "expected newest or oldest"
    );
  return {
    api_version: $,
    total: y(e.total, "activity.total"),
    offset: y(e.offset, "activity.offset"),
    order: t,
    records: x(e.records, "activity.records").map(
      (i, a) => It(i, `activity.records[${String(a)}]`)
    )
  };
}
function Ut(r, e) {
  const t = m(r, e);
  return {
    ready: w(t.ready, `${e}.ready`),
    qualification_percent: U(
      t.qualification_percent,
      `${e}.qualification_percent`
    ),
    valid_evaluation_percent: U(
      t.valid_evaluation_percent,
      `${e}.valid_evaluation_percent`
    ),
    elapsed_hours: U(t.elapsed_hours, `${e}.elapsed_hours`),
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
    blocking_reasons: G(
      t.blocking_reasons,
      `${e}.blocking_reasons`
    ),
    blocking_faults: G(
      t.blocking_faults,
      `${e}.blocking_faults`
    )
  };
}
function Ot(r) {
  const e = m(r, "shadow");
  return k(e, "shadow"), {
    api_version: $,
    readiness: e.readiness === null ? null : Ut(e.readiness, "shadow.readiness"),
    history: x(e.history, "shadow.history").map((t, i) => {
      const a = `shadow.history[${String(i)}]`, n = m(t, a);
      return {
        safety_evaluation_id: u(
          n.safety_evaluation_id,
          `${a}.safety_evaluation_id`
        ),
        evaluated_at_utc: _(
          n.evaluated_at_utc,
          `${a}.evaluated_at_utc`
        ),
        outcome: u(n.outcome, `${a}.outcome`),
        reason_code: u(n.reason_code, `${a}.reason_code`),
        would_command: w(
          n.would_command,
          `${a}.would_command`
        )
      };
    })
  };
}
function Nt(r) {
  const e = m(r, "observation");
  if (k(e, "observation"), e.model_ready_history_available !== !1)
    throw new f(
      "observation.model_ready_history_available",
      "Phase 2 must not claim model-ready history"
    );
  return {
    api_version: $,
    collection_active: w(
      e.collection_active,
      "observation.collection_active"
    ),
    observation_revision: y(
      e.observation_revision,
      "observation.observation_revision"
    ),
    calculated_at_utc: _(
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
    history_boundary: u(
      e.history_boundary,
      "observation.history_boundary"
    )
  };
}
function Rt(r, e) {
  const t = m(r, e);
  return {
    start_utc: _(t.start_utc, `${e}.start_utc`),
    end_utc: _(t.end_utc, `${e}.end_utc`)
  };
}
function Lt(r, e) {
  const t = m(r, e), i = t.value;
  if ((typeof i != "string" || i.length === 0) && (typeof i != "number" || !Number.isFinite(i)))
    throw new f(
      `${e}.value`,
      "expected finite number or text"
    );
  return {
    timestamp_utc: _(t.timestamp_utc, `${e}.timestamp_utc`),
    value: i
  };
}
function Ht(r, e) {
  const t = m(r, e), i = u(t.value_kind, `${e}.value_kind`);
  if (!$t.has(i))
    throw new f(
      `${e}.value_kind`,
      "unsupported provenance"
    );
  if (i === "predicted" || i === "planned")
    throw new f(
      `${e}.value_kind`,
      "future Phase 3/4 series are not accepted by the Phase 2 panel"
    );
  return {
    kind: u(t.kind, `${e}.kind`),
    value_kind: i,
    unit: ne(t.unit, `${e}.unit`),
    source_quality: u(t.source_quality, `${e}.source_quality`),
    coverage_start_utc: _(
      t.coverage_start_utc,
      `${e}.coverage_start_utc`
    ),
    coverage_end_utc: _(
      t.coverage_end_utc,
      `${e}.coverage_end_utc`
    ),
    missing_intervals: x(
      t.missing_intervals,
      `${e}.missing_intervals`
    ).map(
      (a, n) => Rt(a, `${e}.missing_intervals[${String(n)}]`)
    ),
    samples: x(t.samples, `${e}.samples`).map(
      (a, n) => Lt(a, `${e}.samples[${String(n)}]`)
    )
  };
}
function qt(r, e) {
  const t = m(r, e);
  return {
    annotation_id: u(t.annotation_id, `${e}.annotation_id`),
    timestamp_utc: _(t.timestamp_utc, `${e}.timestamp_utc`),
    reason_code: u(t.reason_code, `${e}.reason_code`),
    activity_record_id: u(
      t.activity_record_id,
      `${e}.activity_record_id`
    )
  };
}
function Zt(r) {
  const e = m(r, "timeline");
  if (k(e, "timeline"), e.indoor_prediction_available !== !1)
    throw new f(
      "timeline.indoor_prediction_available",
      "Phase 2 must not claim indoor prediction"
    );
  return {
    api_version: $,
    entry_id: u(e.entry_id, "timeline.entry_id"),
    zone_id: u(e.zone_id, "timeline.zone_id"),
    time_zone: u(e.time_zone, "timeline.time_zone"),
    local_date: u(e.local_date, "timeline.local_date"),
    day_start_utc: _(e.day_start_utc, "timeline.day_start_utc"),
    day_end_utc: _(e.day_end_utc, "timeline.day_end_utc"),
    generated_at_utc: _(
      e.generated_at_utc,
      "timeline.generated_at_utc"
    ),
    indoor_prediction_available: !1,
    capability_statement: u(
      e.capability_statement,
      "timeline.capability_statement"
    ),
    series: x(e.series, "timeline.series").map(
      (t, i) => Ht(t, `timeline.series[${String(i)}]`)
    ),
    annotations: x(e.annotations, "timeline.annotations").map(
      (t, i) => qt(t, `timeline.annotations[${String(i)}]`)
    )
  };
}
function Ft(r) {
  const e = m(r, "narrative");
  return k(e, "narrative"), {
    api_version: $,
    template_version: y(
      e.template_version,
      "narrative.template_version"
    ),
    entry_id: u(e.entry_id, "narrative.entry_id"),
    zone_id: u(e.zone_id, "narrative.zone_id"),
    control_state: u(e.control_state, "narrative.control_state"),
    reason_code: u(e.reason_code, "narrative.reason_code"),
    temperature_c: A(
      e.temperature_c,
      "narrative.temperature_c"
    ),
    hvac_action: ne(e.hvac_action, "narrative.hvac_action"),
    scheduled_target_c: A(
      e.scheduled_target_c,
      "narrative.scheduled_target_c"
    ),
    effective_target_c: A(
      e.effective_target_c,
      "narrative.effective_target_c"
    ),
    next_transition_utc: e.next_transition_utc === null ? null : _(
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
    included_categories: G(
      e.included_categories,
      "narrative.included_categories"
    ),
    rendered: u(e.rendered, "narrative.rendered")
  };
}
class jt {
  constructor(e, t) {
    if (this.hass = e, this.entryId = t, t.length === 0)
      throw new Error("entryId is required");
  }
  async request(e, t, i = {}) {
    const a = await this.hass.callWS({
      type: e,
      api_version: $,
      entry_id: this.entryId,
      ...i
    });
    return t(a);
  }
  configuration() {
    return this.request(
      "intelligent_climate/config/get",
      Dt
    );
  }
  snapshot() {
    return this.request("intelligent_climate/snapshot/get", De);
  }
  activity(e = 0, t = 100, i = "newest") {
    return this.request("intelligent_climate/activity/list", Mt, {
      offset: e,
      limit: t,
      order: i
    });
  }
  shadowStatus() {
    return this.request(
      "intelligent_climate/shadow/status",
      Ot
    );
  }
  observationStatus() {
    return this.request(
      "intelligent_climate/observation/status",
      Nt
    );
  }
  todayTimeline(e) {
    return this.request(
      "intelligent_climate/timeline/today",
      Zt,
      { zone_id: e }
    );
  }
  narrative(e) {
    return this.request(
      "intelligent_climate/narrative/current",
      Ft,
      { zone_id: e }
    );
  }
  schedule() {
    return this.request(
      "intelligent_climate/schedule/get",
      kt
    );
  }
  validateSchedule(e) {
    return this.request(
      "intelligent_climate/schedule/validate",
      St,
      { schedule: e }
    );
  }
  previewSchedule(e, t) {
    return this.request(
      "intelligent_climate/schedule/preview",
      Et,
      t === void 0 ? { schedule: e } : { schedule: e, at_utc: t }
    );
  }
  saveSchedule(e, t) {
    return this.request(
      "intelligent_climate/schedule/save",
      Ct,
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
      (t) => e(De(t)),
      {
        type: "intelligent_climate/subscribe",
        api_version: $,
        entry_id: this.entryId
      }
    );
  }
}
const Ge = ie`
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
function Be(r = globalThis.crypto) {
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
const L = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
], T = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday"
}, X = class X extends P {
  constructor() {
    super(...arguments), this.validationMessage = "", this.saving = !1, this.dirty = !1, this.temperatureUnit = "°C", this.locale = "en-US", this.selectedZoneId = "", this.selectedProfileId = "", this.mobileDay = "monday", this.copyTargets = [], this.zoneChanged = (e) => {
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
      t instanceof HTMLSelectElement && (this.mobileDay = t.value, this.copyTargets = []);
    }, this.copyDay = () => {
      const e = this.mobileDay, t = [...this.copyTargets];
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
    return e === void 0 || t === void 0 ? o`<p role="status">No schedule zone is available.</p>` : o`
      <section class="editor-toolbar" aria-label="Schedule selection">
        <label>
          <span>Zone</span>
          <select .value=${this.selectedZoneId} @change=${this.zoneChanged}>
            ${Object.keys(this.document.zones).map(
      (i) => o`<option value=${i}>${this.zoneName(i)}</option>`
    )}
          </select>
        </label>
        <label>
          <span>Profile</span>
          <select
            .value=${this.selectedProfileId}
            @change=${this.profileChanged}
          >
            ${e.profiles.map(
      (i) => o`<option value=${i.profile_id}>${i.name}</option>`
    )}
          </select>
        </label>
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

      <section class="template-tools" aria-labelledby="template-heading">
        <div>
          <h3 id="template-heading">Starter templates</h3>
          <p>
            Replace the selected profile’s matching days with editable periods.
          </p>
        </div>
        <button type="button" @click=${() => this.applyTemplate("weekday")}>
          Apply weekdays
        </button>
        <button type="button" @click=${() => this.applyTemplate("weekend")}>
          Apply weekend
        </button>
      </section>

      <label class="mobile-day-picker">
        <span>Day to edit</span>
        <select .value=${this.mobileDay} @change=${this.mobileDayChanged}>
          ${L.map(
      (i) => o`<option value=${i}>${T[i]}</option>`
    )}
        </select>
      </label>

      <section class="week-grid" aria-label="Weekly schedule">
        ${L.map((i) => this.renderDay(t, i))}
      </section>

      <section class="copy-tool" aria-labelledby="copy-heading">
        <div>
          <h3 id="copy-heading">Copy ${T[this.mobileDay]}</h3>
          <p>Copied periods receive new stable identities.</p>
        </div>
        <div class="copy-days">
          ${L.filter((i) => i !== this.mobileDay).map(
      (i) => o`<label>
                <input
                  type="checkbox"
                  .checked=${this.copyTargets.includes(i)}
                  @change=${(a) => this.copyTargetChanged(i, a)}
                />
                ${T[i]}
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
      ${this.validationMessage.length === 0 ? h : o`<div class="validation" role="alert">
              <strong>Schedule needs attention</strong>
              <p>${this.validationMessage}</p>
            </div>`}
    `;
  }
  renderDay(e, t) {
    const i = e.days[t], a = t === this.mobileDay ? "" : "mobile-hidden";
    return o`<article class="day-column ${a}">
      <header>
        <div>
          <h3>${T[t]}</h3>
          <span
            >${i.length}
            ${i.length === 1 ? "period" : "periods"}</span
          >
        </div>
        <button
          type="button"
          class="add"
          aria-label=${`Add ${T[t]} period`}
          @click=${() => this.addPeriod(t)}
        >
          + Add
        </button>
      </header>
      ${i.length === 0 ? o`<p class="inheritance">
              ↺ Inherits the most recent period from an earlier day.
            </p>` : i[0]?.local_start === "00:00" ? h : o`<p class="inheritance">
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
    return o`<li
      class="period ${a ? "current" : ""} ${s ? "invalid" : ""}"
    >
      <div class="period-heading">
        <strong
          >${a ? "● Current period" : `Period ${String(i + 1)}`}</strong
        >
        <div>
          <button
            type="button"
            aria-label=${`Duplicate ${T[e]} period ${String(i + 1)}`}
            @click=${() => this.duplicatePeriod(e, i)}
          >
            Duplicate
          </button>
          <button
            type="button"
            class="danger"
            aria-label=${`Delete ${T[e]} period ${String(i + 1)}`}
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
      (l) => o`<option value=${l}>${this.titleCase(l)}</option>`
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
    ) : o`${this.temperatureInput(e, i, "heat_target_c", "Heat target", t.target.heat_target_c)}
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
      ${s ? o`<p class="field-error">Review this period and the validation summary.</p>` : h}
    </li>`;
  }
  temperatureInput(e, t, i, a, n) {
    return o`<label>
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
      return o`<section class="preview-card">
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
    return o`<section class="preview-card" aria-labelledby="preview-heading">
      <div>
        <h3 id="preview-heading">Authoritative preview</h3>
        <span
          >Week of ${t.preview_week_start_local} ·
          ${t.time_zone}</span
        >
      </div>
      ${i === void 0 ? o`<p>
              This zone is disabled, so it has no active scheduled target.
            </p>` : o`<dl>
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
      ${a.length === 0 ? o`<p class="no-warning">
              ✓ No scheduled boundary crosses a DST gap or repeated hour in this
              preview week.
            </p>` : o`<ul class="dst-warnings">
              ${a.map(
      (n) => o`<li>
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
  periodTextChanged(e, t, i, a) {
    const n = a.currentTarget;
    (n instanceof HTMLInputElement || n instanceof HTMLSelectElement) && this.updateProfile((s) => {
      const l = s.days[e][t];
      l !== void 0 && (i === "occupancy_label" ? l.occupancy_label = n.value : l[i] = n.value, s.days[e].sort(
        (c, p) => c.local_start.localeCompare(p.local_start)
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
      const c = l.days[e][t];
      c !== void 0 && i !== "kind" && (c.target[i] = this.celsiusTemperature(s));
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
  applyTemplate(e) {
    const t = e === "weekday" ? L.slice(0, 5) : L.slice(5), i = e === "weekday" ? [
      ["06:30", "Morning", 21],
      ["08:30", "Day", 18],
      ["17:30", "Evening", 21],
      ["22:30", "Sleep", 18]
    ] : [
      ["08:00", "Morning", 21],
      ["23:00", "Sleep", 18]
    ];
    this.updateProfile((a) => {
      for (const n of t)
        a.days[n] = i.map(([s, l, c]) => ({
          ...this.newPeriod(s),
          label: l,
          occupancy_label: l === "Sleep" ? "sleep" : "home",
          target: {
            kind: "single",
            target_c: c,
            heat_target_c: null,
            cool_target_c: null
          }
        }));
    });
  }
  newPeriod(e) {
    return {
      period_id: this.uuid(),
      local_start: e,
      label: "",
      occupancy_label: "none",
      target: {
        kind: "single",
        target_c: 22,
        heat_target_c: null,
        cool_target_c: null
      },
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
    return Be();
  }
  zoneName(e) {
    return this.zones.find((t) => t.zone_id === e)?.name ?? e;
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
X.properties = {
  document: { attribute: !1 },
  zones: { attribute: !1 },
  preview: { attribute: !1 },
  validationMessage: { type: String },
  saving: { type: Boolean },
  dirty: { type: Boolean },
  temperatureUnit: { type: String },
  locale: { type: String },
  selectedZoneId: { state: !0 },
  selectedProfileId: { state: !0 },
  mobileDay: { state: !0 },
  copyTargets: { state: !0 }
}, X.styles = [
  Ge,
  ie`
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
      .template-tools,
      .copy-tool,
      .preview-card,
      .save-bar {
        border: 1px solid var(--ic-border);
        border-radius: 16px;
        background: var(--ic-surface);
        padding: 16px;
        margin-block: 16px;
      }
      .template-tools {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .template-tools div:first-child {
        margin-inline-end: auto;
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
        grid-template-columns: minmax(180px, 1fr) 2fr auto;
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
          align-items: stretch;
          flex-wrap: wrap;
        }
        .template-tools div:first-child {
          inline-size: 100%;
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
        .template-tools button {
          inline-size: 100%;
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
let de = X;
customElements.define("ic-schedule-editor", de);
const Gt = {
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
}, Bt = {
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
}, K = 30, Q = 155, Vt = Q - K, Pe = [30, 61.25, 92.5, 123.75, 155], Wt = 300 * 1e3, Yt = 900 * 1e3;
function ue(r) {
  return Gt[r] ?? r.replaceAll("_", " ");
}
function Ve(r) {
  return typeof r == "string" ? Bt[r] ?? ue(r) : String(r);
}
function Kt(r) {
  return r.filter(
    (e, t) => t === 0 || r[t - 1]?.value !== e.value
  );
}
function Qt(r) {
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
      return Ve(r);
  }
}
function W(r) {
  return r.samples.filter(
    (e) => typeof e.value == "number"
  );
}
function Jt(r, e) {
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
const ee = class ee extends P {
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
      return o`<div class="empty" role="status">
        Today’s timeline is not available yet. Observation continues normally.
      </div>`;
    const e = this.timeline, t = this.temperatureRange(e), i = this.chartWindow(e), a = this.renderedSeries(e, t, i), n = a.find(
      (d) => d.kind === "effective_temperature"
    ), s = n?.sampleCount ?? 0, l = s >= 2, c = e.series.filter(
      (d) => ["hvac_action", "fan_action"].includes(d.kind)
    ), p = this.currentCursor(i), g = this.axisTimes(i, e);
    return o`
      <div class="legend" aria-label="Timeline legend">
        ${a.map(
      (d) => o`<span class="legend-item">
              <span
                class="swatch ${d.className}"
                aria-hidden="true"
              ></span>
              ${d.label}
              <small>${d.valueKind}</small>
            </span>`
    )}
      </div>
      ${a.length === 0 ? o`<div class="empty" role="status">
              No numeric observations yet.
            </div>` : l ? o`<div class="chart-wrap">
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
                    ${Pe.map(
      (d) => C`<line x1="80" x2="970" y1=${d} y2=${d}></line>`
    )}
                    ${[80, 303, 525, 748, 970].map(
      (d) => C`<line
                          x1=${d}
                          x2=${d}
                          y1=${K}
                          y2=${Q}
                        ></line>`
    )}
                  </g>
                  <g class="y-axis-labels" aria-hidden="true">
                    ${Pe.map((d, v) => {
      const [b, S] = t, Ye = S - (S - b) * v / 4;
      return C`<text x="72" y=${d + 6} text-anchor="end">
                        ${le(
        Ye,
        this.temperatureUnit,
        this.locale
      )}
                      </text>`;
    })}
                  </g>
                  ${a.map(
      (d) => C`<g class="series-group ${d.className}">
                        <path
                          class="series ${d.className}"
                          d=${d.path}
                        ></path>
                        ${d.kind === "effective_temperature" ? d.points.map(
        (v) => C`<circle
                                    class="sample-point measured-temperature"
                                    cx=${v.x}
                                    cy=${v.y}
                                    r="4.5"
                                  ></circle>`
      ) : h}
                      </g>`
    )}
                  ${p === null ? h : C`<line
                          class="now"
                          x1=${p}
                          x2=${p}
                          y1=${K - 5}
                          y2=${Q + 5}
                        ></line>`}
                  ${e.annotations.map((d) => {
      const v = this.xPosition(
        Date.parse(d.timestamp_utc),
        i
      );
      return C`<g class="annotation" aria-hidden="true">
                      <circle cx=${v} cy="15" r="6"></circle>
                      <line x1=${v} x2=${v} y1="21" y2=${K + 6}></line>
                    </g>`;
    })}
                  <g class="axis-labels" aria-hidden="true">
                    <text x="80" y="198">${g[0]}</text>
                    <text x="525" y="198" text-anchor="middle">
                      ${g[1]}
                    </text>
                    <text x="970" y="198" text-anchor="end">
                      ${g[2]}
                    </text>
                  </g>
                </svg>
                ${this.sampleSummary(n)}
              </div>` : o`<div class="empty collecting" role="status">
                <div>
                  <strong>Collecting climate history</strong>
                  <p>
                    ${s} of 2 temperature samples collected. The
                    chart will appear after the next observation.
                  </p>
                  ${this.sampleSummary(n)}
                </div>
              </div>`}
      ${c.length === 0 ? h : o`<div class="state-bands" aria-label="Equipment state timeline">
              ${c.map((d) => this.renderStateSeries(d))}
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
      (d) => o`<tr>
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
    return e.series.filter(
      (n) => W(n).length > 0 && n.unit !== "%"
    ).map((n) => {
      const s = W(n), l = s.map((p) => ({
        x: this.xPosition(Date.parse(p.timestamp_utc), i),
        y: this.yPosition(p.value, t)
      })), c = s.at(-1);
      if (c === void 0)
        throw new Error("validated timeline series unexpectedly empty");
      return {
        kind: n.kind,
        valueKind: n.value_kind,
        label: ue(n.kind),
        className: `${n.value_kind} ${n.kind}`,
        path: Jt(l, n.value_kind !== "measured"),
        points: l,
        latest: c.value,
        latestTimestamp: c.timestamp_utc,
        sampleCount: s.length,
        coverage: `${H(
          n.coverage_start_utc,
          this.locale,
          e.time_zone
        )} – ${H(
          n.coverage_end_utc,
          this.locale,
          e.time_zone
        )}`,
        gaps: n.missing_intervals.length
      };
    });
  }
  temperatureRange(e) {
    return this.range(
      e.series.filter((t) => t.unit === "°C").flatMap(
        (t) => W(t).map((i) => i.value)
      )
    );
  }
  sampleSummary(e) {
    return e === void 0 ? h : o`<p class="sample-summary">
      Latest sample
      ${H(
      e.latestTimestamp,
      this.locale,
      this.timeline?.time_zone
    )}
      · Source: effective zone temperature
    </p>`;
  }
  renderStateSeries(e) {
    const t = Kt(e.samples);
    return o`<div class="state-row">
        <strong>${ue(e.kind)}</strong>
        <div>
          ${t.map(
      (i) => o`<span class="state-chip">
                ${this.stateTimestamp(i)}: ${Ve(i.value)}
              </span>`
    )}
        </div>
      </div>
      ${e.kind === "hvac_action" ? o`<div class="state-row derived">
              <strong>Air handler <small>derived</small></strong>
              <div>
                ${t.map(
      (i) => o`<span class="state-chip">
                      ${this.stateTimestamp(i)}:
                      ${Qt(i.value)}
                    </span>`
    )}
              </div>
            </div>` : h}`;
  }
  stateTimestamp(e) {
    return H(
      e.timestamp_utc,
      this.locale,
      this.timeline?.time_zone
    );
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
    return Q - (e - i) / (a - i) * Vt;
  }
  currentCursor(e) {
    const t = Date.now();
    return t < e.start || t > e.end ? null : this.xPosition(t, e);
  }
  chartWindow(e) {
    const t = Date.parse(e.day_start_utc), i = Date.parse(e.day_end_utc), a = e.series.filter((b) => b.unit !== "%").flatMap(
      (b) => W(b).map(
        (S) => Date.parse(S.timestamp_utc)
      )
    ).filter((b) => Number.isFinite(b));
    if (a.length === 0)
      return { start: t, end: i };
    const n = Math.min(...a), s = Math.max(...a), l = i - t, c = Math.max(
      Yt,
      s - n + Wt * 2
    ), p = Math.min(l, c), g = (n + s) / 2;
    let d = g - p / 2, v = g + p / 2;
    return d < t && (d = t, v = t + p), v > i && (v = i, d = i - p), { start: d, end: v };
  }
  axisTimes(e, t) {
    const i = new Intl.DateTimeFormat(this.locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: t.time_zone
    });
    return [
      i.format(new Date(e.start)),
      i.format(new Date((e.start + e.end) / 2)),
      i.format(new Date(e.end))
    ];
  }
  latestValue(e) {
    return typeof e.latest != "number" ? e.latest : le(e.latest, this.temperatureUnit, this.locale);
  }
};
ee.properties = {
  timeline: { attribute: !1 },
  locale: { type: String },
  temperatureUnit: { type: String, attribute: "temperature-unit" }
}, ee.styles = ie`
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
let pe = ee;
customElements.get("ic-today-timeline") || customElements.define("ic-today-timeline", pe);
const he = "intelligent-climate.temperature-unit";
function Xt() {
  try {
    const r = window.localStorage.getItem(he);
    if (r === "fahrenheit" || r === "celsius")
      return r;
  } catch {
  }
  return "home_assistant";
}
function ei(r) {
  try {
    r === "home_assistant" ? window.localStorage.removeItem(he) : window.localStorage.setItem(he, r);
  } catch {
  }
}
function ti(r, e) {
  return r === "fahrenheit" ? "°F" : r === "celsius" ? "°C" : e;
}
const ii = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
];
function ri(r, e, t = /* @__PURE__ */ new Date()) {
  const i = ni(
    e.config.equipment_group,
    "config.equipment_group"
  ), a = Me(
    i.equipment_group_id,
    "config.equipment_group.equipment_group_id"
  ), n = Me(
    e.config.acknowledged_time_zone,
    "config.acknowledged_time_zone"
  ), s = {};
  for (const l of e.zones) {
    const c = Be();
    s[l.zone_id] = {
      zone_id: l.zone_id,
      enabled: !1,
      selected_profile_id: c,
      profiles: [ai(c)]
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
function Ie(r, e = /* @__PURE__ */ new Date()) {
  return { ...structuredClone(r), saved_at_utc: e.toISOString() };
}
function ai(r) {
  const e = {};
  for (const t of ii)
    e[t] = [];
  return {
    profile_id: r,
    name: "Normal",
    enabled: !0,
    days: e
  };
}
function ni(r, e) {
  if (typeof r != "object" || r === null || Array.isArray(r))
    throw new Error(`${e} is unavailable`);
  return r;
}
function Me(r, e) {
  if (typeof r != "string" || r.length === 0)
    throw new Error(`${e} is unavailable`);
  return r;
}
const We = [
  { id: "overview", label: "Overview", icon: "⌂" },
  { id: "schedule", label: "Schedule", icon: "▦" },
  { id: "sensors", label: "Sensors", icon: "◫" },
  { id: "activity", label: "Activity", icon: "↯" },
  { id: "settings", label: "Settings", icon: "⚙" }
];
function si(r) {
  return We.some((e) => e.id === r);
}
const te = class te extends P {
  constructor() {
    super(...arguments), this.narrow = !1, this.activeRoute = "overview", this.selectedEntryId = "", this.selectedZoneId = "", this.loading = !0, this.errorMessage = "", this.activityFilter = "all", this.temperatureUnitPreference = Xt(), this.activityLoadingOlder = !1, this.scheduleLoading = !1, this.scheduleSaving = !1, this.scheduleDirty = !1, this.scheduleMessage = "", this.scheduleConflict = !1, this.loadGeneration = 0, this.detailLoadGeneration = 0, this.entryChanged = (e) => {
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
      i !== "home_assistant" && i !== "fahrenheit" && i !== "celsius" || (this.temperatureUnitPreference = i, ei(i));
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
          const e = Ie(this.scheduleDocument);
          await this.client.validateSchedule(e), this.schedulePreview = await this.client.previewSchedule(e);
        } catch (e) {
          this.schedulePreview = void 0, this.scheduleMessage = this.describeScheduleError(e);
        }
      }
    }, this.saveSchedule = async () => {
      if (!(this.client === void 0 || this.scheduleDocument === void 0 || this.scheduleSaving)) {
        this.scheduleSaving = !0, this.scheduleMessage = "", this.scheduleConflict = !1;
        try {
          const e = this.scheduleDocument.revision, t = Ie(this.scheduleDocument);
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
      t !== void 0 && si(t) && (this.activeRoute = t);
    }
  }
  updated(e) {
    (e.has("hass") || e.has("panel")) && this.client === void 0 && this.initialize();
  }
  render() {
    const e = this.entries();
    return o`
      <div class="app-shell">
        <header class="topbar">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">IC</span>
            <div>
              <h1>Intelligent Climate</h1>
              <p>See what your home is doing—and why.</p>
            </div>
          </div>
          ${e.length > 1 ? o`<label class="entry-picker">
                  <span>Equipment group</span>
                  <select
                    .value=${this.selectedEntryId}
                    @change=${this.entryChanged}
                  >
                    ${e.map(
      (t) => o`<option value=${t.entry_id}>
                          ${t.title}
                        </option>`
    )}
                  </select>
                </label>` : o`<div class="entry-name">
                  ${e[0]?.title ?? "Climate"}
                </div>`}
        </header>

        <nav class="primary-nav" aria-label="Intelligent Climate sections">
          ${We.map(
      (t) => o`<button
                type="button"
                class=${this.activeRoute === t.id ? "active" : ""}
                aria-current=${this.activeRoute === t.id ? "page" : h}
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
    return o`<div class="loading" role="status" aria-live="polite">
      <div class="spinner" aria-hidden="true"></div>
      <strong>Loading your climate picture…</strong>
      <span>Connecting to the local Intelligent Climate data.</span>
    </div>`;
  }
  renderError() {
    return o`<section class="error-card" role="alert">
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
    return o`
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
      ${this.scheduleLoading ? o`<div class="loading" role="status">Loading schedule…</div>` : this.scheduleDocument === void 0 ? o`<section class="error-card" role="alert">
                <div>
                  <h3>Schedule is unavailable</h3>
                  <p>${this.scheduleMessage}</p>
                  <button type="button" @click=${this.reloadSchedule}>
                    Try again
                  </button>
                </div>
              </section>` : o`${this.scheduleConflict ? o`<section class="schedule-conflict" role="alert">
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
                      </section>` : h}
                <ic-schedule-editor
                  .document=${this.scheduleDocument}
                  .zones=${e.configuration.zones}
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
    const e = this.requireData(), t = _t(e.snapshot.control_state), i = e.shadow.readiness, a = [
      "shadow_qualifying",
      "shadow_ready"
    ].includes(e.snapshot.control_state), n = this.selectedZone();
    return o`
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
              >${e.snapshot.reason_code === null ? "No current alert" : V(e.snapshot.reason_code)}</span
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
          ${this.narrative === void 0 ? o`<p class="muted">
                  A current explanation is not available yet.
                </p>` : o`<p class="narrative">${this.renderNarrative()}</p>`}
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
          ${a ? i === null ? o`<p class="muted">
                    Scheduled Shadow is starting. Qualification evidence will
                    appear after its first valid evaluation.
                  </p>` : o`<div class="progress-row">
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
                    ${i.blocking_reasons.length === 0 ? h : o`<p class="blocking">
                            <strong>Still needed:</strong>
                            ${i.blocking_reasons.map((s) => s.replaceAll("_", " ")).join(", ")}
                          </p>`}
                    ${i.blocking_faults.length === 0 ? h : o`<p class="fault">
                            <strong>Blocking fault:</strong>
                            ${i.blocking_faults.join(", ")}
                          </p>`}` : o`<p class="muted">
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
    return e.length < 2 ? h : o`<div
      class="zone-tabs"
      role="tablist"
      aria-label="Climate zones"
    >
      ${e.map(
      (t) => o`<button
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
    return o`
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
      return o`<article class="card zone-health-card">
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
            ${i?.sensor_data_degraded === !0 ? o`<p class="warning-copy">Temperature source data is degraded.</p>` : h}
            ${i?.thermostat_data_degraded === !0 ? o`<p class="warning-copy">Thermostat observation data is degraded.</p>` : h}
            ${this.enabledSourceCount(t.humidity_sources) === 0 ? o`<p class="muted">Humidity is not configured for this zone. Reconfigure the zone to select a humidity sensor or thermostat.</p>` : h}
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
    return o`
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
        ${e.activity.records.length < e.activity.total ? o`<button
                type="button"
                class="load-more"
                ?disabled=${this.activityLoadingOlder}
                @click=${this.loadOlderActivity}
              >
                ${this.activityLoadingOlder ? "Loading…" : "Load older activity"}
              </button>` : h}
      </section>
    `;
  }
  renderActivityRecords(e) {
    return e.length === 0 ? o`<div class="empty-state" role="status">
        No matching material activity is available.
      </div>` : o`<ol class="activity-list">
      ${e.map((t) => {
      const i = this.data?.configuration.zones.find(
        (a) => a.zone_id === t.zone_id
      );
      return o`<li>
          <span
            class="activity-marker severity-${t.severity}"
            aria-hidden="true"
          ></span>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${V(t.activity_type)}</strong
              ><time datetime=${t.timestamp_utc}
                >${this.time(t.timestamp_utc)}</time
              >
            </div>
            <p>${t.explanation}</p>
            <div class="activity-meta">
              <span>${V(t.reason_code)}</span
              >${i === void 0 ? h : o`<span>${i.name}</span>`}<span>${t.severity}</span>${this.repairRecordStatus(t)}
            </div>
          </div>
        </li>`;
    })}
    </ol>`;
  }
  renderSettings() {
    const e = this.requireData(), t = e.configuration.config.automation_enabled === !0, i = e.configuration.options.safety_limits;
    return o`
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
    return ti(
      this.temperatureUnitPreference,
      this.hass.config.unit_system.temperature
    );
  }
  temperature(e) {
    return le(e, this.temperatureUnit(), this.locale());
  }
  humidity(e, t = !0) {
    return t ? e === null ? "Unavailable" : `${new Intl.NumberFormat(this.locale(), { maximumFractionDigits: 1 }).format(e)}%` : "Not configured";
  }
  time(e) {
    return H(e, this.locale(), this.timeline?.time_zone);
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
      }[e.control_state] ?? `Current status: ${V(e.control_state)}.`
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
      return h;
    const t = this.data?.configuration.active_repairs.includes(e.reason_code) === !0;
    return o`<span class=${t ? "repair-active" : "repair-history"}
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
    const i = new jt(this.hass, e);
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
        this.scheduleDocument = t.schedule ?? ri(this.selectedEntryId, this.data.configuration), this.schedulePreview = void 0, this.scheduleDirty = !1, this.scheduleConflict = !1;
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
    return e instanceof f ? `The backend returned data this frontend cannot safely display (${e.message}). Reload the integration or update the candidate.` : e instanceof Error ? e.message : "An unknown local data error occurred.";
  }
  navigate(e) {
    this.confirmDiscard(e) && (this.activeRoute = e, window.history.replaceState(null, "", `/intelligent-climate/${e}`), this.shadowRoot?.querySelector("#main-content")?.focus(), e === "schedule" && this.scheduleDocument === void 0 && this.loadSchedule(this.loadGeneration));
  }
  selectZone(e) {
    this.selectedZoneId = e, this.loadZoneDetails(this.loadGeneration);
  }
  confirmDiscard(e) {
    return !this.scheduleDirty || e === "schedule" || window.confirm("Discard unsaved schedule changes?");
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
te.properties = {
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
}, te.styles = [
  Ge,
  ie`
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
let me = te;
customElements.get("intelligent-climate-panel") || customElements.define("intelligent-climate-panel", me);
