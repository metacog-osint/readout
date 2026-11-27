/* Readout page: renders data/snapshot.json. All text from data goes through esc(). */
(function () {
  "use strict";

  var T = window.TicTime;

  function esc(v) {
    return String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function when(iso) {
    // House rule: the viewer's own zone by default, the zone always named, changed from the Time menu.
    if (!iso) { return ""; }
    if (T) { try { return T.format(iso, { year: true }); } catch (e) { /* fall through */ } }
    try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZoneName: "short" }); } catch (e) { return iso; }
  }
  // A statement with a date only (EEAS, UN, AU) is shown as a date, never shifted into the viewer's zone.
  function stamp(i) { return i.time_precision === "day" ? String(i.published_at).slice(0, 10) : when(i.published_at); }
  function num(n) { return Number(n || 0).toLocaleString("en-US"); }
  function link(url, label) { return '<a href="' + esc(url) + '" rel="noopener">' + esc(label) + "</a>"; }
  function hrs(h) { return (h > 0 ? "+" : "") + h + " h"; }

  var S, NAMES, statements = [], councils = [], filtered = [];
  var CALM = { deescalation: 1, denial: 1, assurance: 1 };
  var SPEAKER = { kremlin: "Kremlin", govuk: "UK government", eeas: "EU (EEAS)", unsc: "UN Security Council", aupsc: "AU PSC" };
  var PROG = { watchfloor: "Watchfloor", noisefloor: "Noisefloor", wake: "Wake", blackout: "Blackout", cordon: "Cordon", launch: "Launch" };
  function cname(c) { return NAMES[c] || c; }
  function places(list) { return (list || []).map(cname).join(", "); }
  function claimBadge(c) { return c && c !== "none" ? '<span class="claim claim-' + esc(c) + '">' + esc(c) + "</span>" : '<span class="muted small">none</span>'; }
  function words(i) {
    var w = [];
    Object.keys(i.claims || {}).forEach(function (k) { (i.claims[k] || []).forEach(function (x) { w.push(x); }); });
    return w.length ? '<div class="small muted">Words: ' + esc(w.join(", ")) + "</div>" : "";
  }

  function tiles() {
    var calm = statements.filter(function (i) { return i.say_do && i.say_do.calm; });
    var gaps = statements.filter(function (i) { return i.say_do && i.say_do.candidate_gap; });
    var paired = calm.filter(function (i) { return i.say_do.pairs > 0; });
    document.getElementById("tiles").innerHTML = [
      ["Statements read", num(statements.length)],
      ["Calm claims", num(calm.length)],
      ["Calm claims with activity nearby", num(paired.length)],
      ["Candidate say-do gaps (proposed rule)", num(gaps.length)],
      ["Suite items held for the check", num((S.tips || []).length)]
    ].map(function (t) { return '<div class="tile"><span class="k">' + esc(t[0]) + '</span><span class="v">' + esc(t[1]) + "</span></div>"; }).join("");
  }

  function pairList(i) {
    var p = (i.say_do && i.say_do.pair_items) || [];
    if (!p.length) { return '<span class="muted small">No anomaly or warning in those countries within 72 hours.</span>'; }
    var more = i.say_do.pairs > p.length ? '<li class="muted">and ' + (i.say_do.pairs - p.length) + " more</li>" : "";
    return '<ul class="pairs">' + p.map(function (x) {
      return "<li>" + esc(PROG[x.program] || x.program) + ": " + (x.link ? link(x.link, x.title || x.item_id) : esc(x.title || x.item_id)) +
        ' <span class="muted">' + esc(x.tier) + ", " + esc(places(x.countries)) + ", " + esc(hrs(x.hours_from_statement)) +
        (x.stale ? ", producer stale" : "") + "</span></li>";
    }).join("") + more + "</ul>";
  }

  function stmtCell(i) {
    var q = (i.quotes || []).map(function (s) { return '<p class="quote">' + esc(s) + "</p>"; }).join("");
    return link(i.url, i.title) + ' <span class="muted small">' + esc(i.doc_type) + "</span>" + words(i) + q;
  }

  function saydo() {
    var rows = statements.filter(function (i) { return i.say_do && i.say_do.calm && i.say_do.pairs > 0; });
    rows.sort(function (a, b) {
      return (b.say_do.candidate_gap - a.say_do.candidate_gap) || (b.say_do.groups.length - a.say_do.groups.length) ||
        (a.published_at < b.published_at ? 1 : -1);
    });
    var t = document.getElementById("saydo");
    if (!rows.length) {
      t.innerHTML = "<tbody><tr><td class='muted'>" + (suiteRead() ? "No calm claim has an anomaly or warning in the countries it names within 72 hours." :
        "The suite's findings were not read on the last run, so the check could not be made.") + "</td></tr></tbody>";
      return;
    }
    t.innerHTML = "<thead><tr><th scope='col'>When</th><th scope='col'>Speaker</th><th scope='col'>Statement</th><th scope='col'>Claim</th><th scope='col'>Countries</th><th scope='col'>Seen nearby</th></tr></thead><tbody>" +
      rows.map(function (i) {
        return '<tr class="stmt-row" id="sd-' + esc(i.id) + '"><td>' + esc(stamp(i)) + "</td><td>" + esc(SPEAKER[i.lane]) + "</td><td>" + stmtCell(i) + "</td><td>" +
          claimBadge(i.claim) + (i.say_do.candidate_gap ? ' <span class="badge gap" title="Proposed rule RO-IND-1: pairs from at least two independent sources">candidate gap</span>' : "") +
          "</td><td>" + esc(places(i.countries_mentioned)) + "</td><td>" + pairList(i) + "</td></tr>";
      }).join("") + "</tbody>";
  }

  function threats() {
    var rows = statements.filter(function (i) { return i.say_do && i.say_do.activity_near_threat; });
    var t = document.getElementById("threats");
    if (!rows.length) { t.innerHTML = "<tbody><tr><td class='muted'>None in this read.</td></tr></tbody>"; return; }
    t.innerHTML = "<thead><tr><th scope='col'>When</th><th scope='col'>Speaker</th><th scope='col'>Statement</th><th scope='col'>Seen nearby</th></tr></thead><tbody>" +
      rows.map(function (i) {
        return "<tr class='stmt-row'><td>" + esc(stamp(i)) + "</td><td>" + esc(SPEAKER[i.lane]) + "</td><td>" + stmtCell(i) + "</td><td>" + pairList(i) + "</td></tr>";
      }).join("") + "</tbody>";
  }

  function suiteRead() { return S.lanes.suite && S.lanes.suite.status === "ok"; }

  function applyFilters() {
    var lane = document.getElementById("f-lane").value, claim = document.getElementById("f-claim").value;
    var q = document.getElementById("f-q").value.trim().toLowerCase();
    filtered = statements.filter(function (i) {
      if (lane && i.lane !== lane) { return false; }
      if (claim === "calm" && !(i.say_do && i.say_do.calm)) { return false; }
      if (claim && claim !== "calm" && i.claim !== claim) { return false; }
      if (q) {
        var hay = [i.title, i.excerpt, places(i.countries_mentioned), JSON.stringify(i.claims || {})].join(" ").toLowerCase();
        if (hay.indexOf(q) < 0) { return false; }
      }
      return true;
    });
    var t = document.getElementById("statements");
    t.innerHTML = "<thead><tr><th scope='col'>When</th><th scope='col'>Speaker</th><th scope='col'>Statement</th><th scope='col'>Claim</th><th scope='col'>Countries named</th></tr></thead><tbody>" +
      filtered.map(function (i) {
        var ex = i.excerpt ? '<div class="small muted">' + esc(i.excerpt) + "</div>" : "";
        return '<tr class="stmt-row" id="' + esc(i.id) + '"><td>' + esc(stamp(i)) + "</td><td>" + esc(SPEAKER[i.lane]) + "</td><td>" +
          link(i.url, i.title) + ' <span class="muted small">' + esc(i.doc_type) + "</span>" + ex + "</td><td>" + claimBadge(i.claim) + words(i) +
          "</td><td>" + esc(places(i.countries_mentioned)) + "</td></tr>";
      }).join("") + "</tbody>";
    document.getElementById("f-count").textContent = filtered.length + " of " + statements.length;
  }

  function votes() {
    var el = document.getElementById("votes");
    var held = ["unsc", "aupsc"].filter(function (k) { return S.lanes[k] && S.lanes[k].status === "held"; });
    var html = held.length ? '<p class="small held">Held: ' + held.map(function (k) { return esc(SPEAKER[k]); }).join(" and ") +
      ". Not read until the terms are cleared.</p>" : "";
    if (councils.length) {
      html += "<div class='scroll'><table><thead><tr><th scope='col'>Date</th><th scope='col'>Body</th><th scope='col'>Record</th><th scope='col'>Outcome</th><th scope='col'>Countries</th></tr></thead><tbody>" +
        councils.map(function (i) {
          var o = i.outcome || {}, out = [];
          if (o.adopted) { out.push("adopted" + (o.unanimous ? " unanimously" : "")); }
          if (o.failed) { out.push("failed to adopt"); }
          if (o.veto) { out.push("veto mentioned"); }
          if (o.presidential_statement) { out.push("presidential statement"); }
          if ((o.resolutions || []).length) { out.push("resolution " + o.resolutions.join(", ")); }
          var label = i.lane === "unsc" ? i.doc : (i.doc_type + (i.meeting ? ", meeting " + i.meeting : ""));
          return "<tr id='" + esc(i.id) + "'><td>" + esc(stamp(i)) + "</td><td>" + esc(SPEAKER[i.lane]) + "</td><td>" + link(i.url, label) +
            "</td><td>" + esc(out.join("; ") || (i.lane === "unsc" ? "meeting" : "")) + "</td><td>" + esc(places(i.countries_mentioned)) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    el.innerHTML = html || "<p class='muted small'>Nothing read.</p>";
  }

  function lanes() {
    var label = { kremlin: "Kremlin Atom feed", govuk: "GOV.UK search API", eeas: "EEAS press material", unsc: "UN Security Council meetings coverage",
      aupsc: "AU Peace and Security Council RSS", suite: "The suite's findings (COP bus and live feeds)" };
    document.getElementById("lanes").innerHTML = "<ul class='small'>" + Object.keys(S.lanes).map(function (k) {
      var l = S.lanes[k];
      var st = l.status === "ok" ? "read " + when(l.fetched_at) + ", " + num(l.items) + " items" :
        l.status === "failed" ? "<strong>not read</strong> on the last run (" + esc(l.error) + ")" + (l.from_previous ? "; showing the last good copy from " + esc(when(l.fetched_at)) : "; nothing to show") :
        l.status === "held" ? '<span class="held">held: terms not cleared</span>' : esc(l.status);
      return "<li>" + esc(label[k] || k) + ": " + st + "</li>";
    }).join("") + "</ul>";
  }

  function render() {
    tiles(); saydo(); threats(); applyFilters(); votes(); lanes();
    document.getElementById("asof").textContent = "Collected " + when(S.generated_at) + " · method " + S.method_version;
    if (location.hash) { var el = document.getElementById(location.hash.slice(1)); if (el) { el.scrollIntoView(); } }
  }

  fetch("data/snapshot.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (data) {
    S = data; NAMES = data.country_names || {};
    statements = S.items.filter(function (i) { return i.lane === "kremlin" || i.lane === "govuk" || i.lane === "eeas"; });
    councils = S.items.filter(function (i) { return i.lane === "unsc" || i.lane === "aupsc"; });
    ["f-lane", "f-claim", "f-q"].forEach(function (id) { document.getElementById(id).addEventListener("input", applyFilters); });
    if (T && T.mountSettings) { T.mountSettings(document.getElementById("time-settings")); }
    if (T && T.onChange) { T.onChange(render); }
    render();
  }).catch(function (e) {
    document.getElementById("asof").textContent = "Could not load the data: " + e;
  });
})();
