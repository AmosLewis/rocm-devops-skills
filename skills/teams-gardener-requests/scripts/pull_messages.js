/*
 * Runs inside the authenticated Microsoft Teams web tab (via CDP Runtime.evaluate,
 * awaitPromise=true). Reads the Teams client's own IndexedDB caches and returns a
 * JSON string describing recent channel messages for the configured channels.
 *
 * It is injected with a leading `var CHANNEL_TOPICS = [...]` line by the Python
 * orchestrator, so this file expects that global to already exist.
 */
(async function () {
  function openDB(name) {
    return new Promise(function (res, rej) {
      var r = indexedDB.open(name);
      r.onerror = function () { rej(r.error); };
      r.onsuccess = function () { res(r.result); };
    });
  }
  function getAll(db, store) {
    return new Promise(function (res, rej) {
      try {
        var t = db.transaction(store, "readonly").objectStore(store).getAll();
        t.onsuccess = function () { res(t.result || []); };
        t.onerror = function () { rej(t.error); };
      } catch (e) { rej(e); }
    });
  }
  function stripHtml(html) {
    if (!html) return "";
    try {
      var doc = new DOMParser().parseFromString(html, "text/html");
      return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
    } catch (e) {
      return String(html).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    }
  }
  function extractPRs(html) {
    var out = [], seen = {}, m;
    var re = /github\.com\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)\/pull\/(\d+)/gi;
    while ((m = re.exec(html))) {
      var key = (m[1] + "/" + m[2] + "#" + m[3]).toLowerCase();
      if (!seen[key]) { seen[key] = 1; out.push({ org: m[1], repo: m[2], number: m[3] }); }
    }
    return out;
  }
  function currentUser() {
    // The signed-in identity is in the MSAL account object cached in localStorage.
    // Each account entry is a JSON blob carrying {name, username, homeAccountId, ...};
    // matching on those fields is tenant- and authority-agnostic (login.windows.net,
    // login.microsoftonline.com, ...), so nothing about the user is hardcoded.
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var v = localStorage.getItem(localStorage.key(i));
        if (!v || v.charAt(0) !== "{") continue;
        var o;
        try { o = JSON.parse(v); } catch (e) { continue; }
        if (o && o.name && o.homeAccountId && (o.username || o.localAccountId)) return o.name;
      }
    } catch (e) {}
    return null;
  }
  function extractMentions(html) {
    if (!html) return [];
    var out = [], seen = {}, m;
    // Teams renders channel mentions as <span itemtype=".../Mention">Name</span> or <at>Name</at>
    var res = [
      /<span[^>]*itemtype="[^"]*[Mm]ention[^"]*"[^>]*>([^<]+)<\/span>/g,
      /<at[^>]*>([^<]+)<\/at>/g
    ];
    res.forEach(function (r) {
      var mm;
      while ((mm = r.exec(html))) {
        var name = mm[1].replace(/\s+/g, " ").trim();
        if (name && !seen[name]) { seen[name] = 1; out.push(name); }
      }
    });
    return out;
  }

  try {
    var dbs = await indexedDB.databases();
    var convName = (dbs.find(function (d) { return /Teams:conversation-manager:/.test(d.name); }) || {}).name;
    var rcName = (dbs.find(function (d) { return /Teams:replychain-manager:/.test(d.name); }) || {}).name;
    if (!convName || !rcName) return JSON.stringify({ error: "Teams IndexedDB not found (conv=" + convName + ", rc=" + rcName + ")" });

    // 1) channel topic -> {threadId, groupId, tenant}
    var convDB = await openDB(convName);
    var convs = await getAll(convDB, "conversations");
    convDB.close();
    var wanted = {};
    CHANNEL_TOPICS.forEach(function (t) { wanted[t] = null; });
    convs.forEach(function (r) {
      var tp = r.threadProperties || {};
      var topic = tp.topic;
      if (topic && wanted.hasOwnProperty(topic) && !wanted[topic]) {
        wanted[topic] = { threadId: r.id, groupId: tp.groupId || null, tenant: tp.tenantid || null };
      }
    });

    // 2) messages per target thread from replychains
    var rcDB = await openDB(rcName);
    var chains = await getAll(rcDB, "replychains");
    rcDB.close();

    var byThread = {};
    Object.keys(wanted).forEach(function (topic) {
      if (wanted[topic]) byThread[wanted[topic].threadId] = topic;
    });

    var msgs = [];
    chains.forEach(function (rc) {
      var topic = byThread[rc.conversationId];
      if (!topic || !rc.messageMap) return;
      Object.values(rc.messageMap).forEach(function (m) {
        if (!m || !m.id) return;
        if (m.messageType && m.messageType.indexOf("RichText") !== 0 && m.messageType !== "Text") return; // skip control/system
        if (m.deletionInfo) return;
        var html = m.content || "";
        msgs.push({
          channel: topic,
          threadId: rc.conversationId,
          id: String(m.id),
          parentId: String(m.parentMessageId || m.id),
          isRoot: String(m.parentMessageId || m.id) === String(m.id),
          author: m.imDisplayName || m.fromDisplayNameInToken || "(unknown)",
          timeMs: Number(m.originalArrivalTime || m.clientArrivalTime || m.id),
          text: stripHtml(html).slice(0, 800),
          prs: extractPRs(html),
          mentions: extractMentions(html)
        });
      });
    });

    return JSON.stringify({
      generatedAtMs: Date.now(),
      currentUser: currentUser(),
      channels: wanted,
      messageCount: msgs.length,
      messages: msgs
    });
  } catch (e) {
    return JSON.stringify({ error: String(e && e.stack || e) });
  }
})();
