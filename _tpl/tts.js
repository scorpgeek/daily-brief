/* ---- listen: the briefing read aloud ----

   The browser's own speech engine, so a briefing still costs nothing to
   build, needs no key, and works on a phone with no connection.

   The text is read in blocks -- paragraphs, list items, tables -- rather
   than as one long utterance. Two reasons. Chrome silently truncates an
   utterance at about fifteen seconds, and a single utterance gives nowhere
   to show how far the reading has got. Blocks also make the word
   highlighting possible, because the offsets the engine reports line up
   with the text nodes of one block.

   A keep-alive timer pauses and resumes the utterance every nine seconds,
   which is the long-standing workaround for that same Chrome bug on the
   occasional block that still runs long. */

(function(){
  var synth = window.speechSynthesis;
  var dlg = document.getElementById('tts');
  if(!synth || !dlg) return;

  var elNow   = document.getElementById('ttsNow');
  var elList  = document.getElementById('ttsList');
  var elPlay  = document.getElementById('ttsPlay');
  var elStop  = document.getElementById('ttsStop');
  var elBack  = document.getElementById('ttsBack');
  var elRate  = document.getElementById('ttsRate');
  var elVoice = document.getElementById('ttsVoice');
  var elVoiceNote = document.getElementById('ttsVoiceNote');
  var elClose = document.getElementById('ttsClose');

  var rate = 1, voice = null, units = [], queue = [], qi = -1;
  var cur = null, keep = null, playing = false, stopped = true;
  var markEl = null, lastUnit = null;
  var gen = 0, curIndex = 0, offset = 0;

  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  /* ---- reading units ---------------------------------------------- */

  function titleOf(el){
    var h = el.querySelector('h2.sec, summary');
    if(!h) return '';
    var n = h.querySelector('.n, .sec-n'), f = h.querySelector('.sec-flag');
    var s = h.textContent || '';
    if(n) s = s.replace(n.textContent, '');
    if(f) s = s.replace(f.textContent, '');
    return s.replace(/\s+/g, ' ').trim();
  }

  function numOf(el){
    var h = el.querySelector('h2.sec, summary');
    var n = h && h.querySelector('.n, .sec-n');
    return n ? n.textContent.trim() : '';
  }

  /* One band mechanism for both editions. The desk marks each section with
     data-band; the phone marks each band wrapper, and the section inherits
     it from there. */
  function bandOf(el){
    var host = (el.dataset && el.dataset.band) ? el : el.closest('[data-band]');
    return (host && host.dataset) ? host.dataset.band : '';
  }

  function unitsOf(){
    var out = [];
    Array.prototype.forEach.call(
      document.querySelectorAll('section[id], details[data-sec]'),
      function(el){
        if(el.closest('dialog') || el.closest('.rail')) return;
        out.push({el:el, num:numOf(el), title:titleOf(el), band:bandOf(el)});
      });
    return out;
  }

  /* ---- text extraction --------------------------------------------- */

  /* Leaf blocks only. A list item containing a paragraph is read once, as
     the item, rather than twice.

     A <dt> is paired with the <dd> that follows it, and read as one
     chunk. The "30 seconds" block and My Lens are both definition lists,
     and reading the label on its own -- "What", "Today" -- before the
     sentence it belongs to is a stutter. As one chunk it reads "What.
     Delhi pandal organisers say an earlier forced closing time is making
     crowd control worse." */
  var BLOCKS = 'p,li,h4,h5,dt,dd,blockquote,table';

  function blocksOf(el){
    var out = [];
    Array.prototype.forEach.call(el.querySelectorAll(BLOCKS), function(n){
      if(n.querySelector(BLOCKS)) return;
      var els = [n];
      if(n.tagName === 'DT'){
        var sib = n.nextElementSibling;
        if(sib && sib.tagName === 'DD') els.push(sib);
      }
      out.push({el:n, els:els});
    });
    return out;
  }

  /* The text and the text nodes it came from. The engine reports word
     offsets into the string it was given, so the string has to be built the
     same way when speaking and when highlighting. */
  function walkMany(els){
    var parts = [], text = '', n;
    els.forEach(function(el){
      if(text && !/\s$/.test(text)){ text += ' '; }
      var walker = document.createTreeWalker(el, 4);
      while((n = walker.nextNode())){
        var t = (n.nodeValue || '').replace(/\s+/g, ' ');
        if(!t) continue;
        parts.push({node:n, text:t, start:text.length});
        text += t;
      }
    });
    return {parts:parts, text:text};
  }

  function textOf(item){
    var block = item.el;
    if(block.tagName === 'TABLE'){
      var rows = [];
      var cap = block.querySelector('caption');
      if(cap){
        var c = (cap.textContent || '').replace(/\s+/g, ' ').trim();
        if(c) rows.push(c);
      }
      Array.prototype.forEach.call(block.querySelectorAll('tr'), function(tr){
        var cells = [];
        Array.prototype.forEach.call(tr.children, function(td){
          cells.push((td.textContent || '').replace(/\s+/g, ' ').trim());
        });
        if(cells.length) rows.push(cells.join(', '));
      });
      return rows.join('. ');
    }
    return walkMany(item.els).text;
  }

  function buildQueue(){
    queue = [];
    units.forEach(function(u){
      blocksOf(u.el).forEach(function(bl){
        var t = textOf(bl);
        if(t && t.length) queue.push({
          unit:u, els:bl.els, full:t,
          /* A table is read cell by cell with commas, which is the right
             thing to hear and the wrong thing to highlight against -- the
             spoken text and the DOM text do not line up. So tables are
             read but not marked. */
          markable: bl.el.tagName !== 'TABLE'
        });
      });
    });
  }

  /* ---- highlighting ------------------------------------------------- */

  function clearMark(){
    if(!markEl) return;
    var parent = markEl.parentNode, txt = markEl.textContent;
    if(parent) parent.replaceChild(document.createTextNode(txt), markEl);
    markEl = null;
  }

  function mark(els, start, len){
    clearMark();
    if(!len) return;
    var w = walkMany(els);
    if(start >= w.text.length) return;
    var part = null, off = 0;
    for(var i = 0; i < w.parts.length; i++){
      var p = w.parts[i];
      if(start < p.start + p.text.length){ part = p; off = start - p.start; break; }
    }
    if(!part) return;
    var node = part.node, full = node.nodeValue;
    var s = Math.max(0, off);
    var e = Math.min(full.length, off + len);
    if(e <= s) return;
    var parent = node.parentNode;
    if(!parent) return;
    var sp = document.createElement('span');
    sp.className = 'spoken';
    sp.textContent = full.slice(s, e);
    if(s > 0) parent.insertBefore(document.createTextNode(full.slice(0, s)), node);
    var tail = null;
    if(e < full.length) tail = document.createTextNode(full.slice(e));
    parent.replaceChild(sp, node);
    if(tail) parent.insertBefore(tail, sp.nextSibling);
    markEl = sp;
  }

  /* ---- the section list --------------------------------------------- */

  function buildList(){
    var tpl = document.getElementById('ttsRow');
    if(!tpl) return;
    var frag = document.createDocumentFragment();
    var band = null;
    units.forEach(function(u, i){
      var b = u.band || 'Start';
      if(b !== band){
        band = b;
        var g = document.createElement('div');
        g.className = 'tts-g';
        g.textContent = b;
        frag.appendChild(g);
      }
      var row = tpl.content.firstElementChild.cloneNode(true);
      row.setAttribute('data-i', i);
      row.querySelector('.n').textContent = u.num || '';
      row.querySelector('.t').textContent = u.title || '30 seconds';
      frag.appendChild(row);
    });
    elList.innerHTML = '';
    elList.appendChild(frag);
    Array.prototype.forEach.call(elList.querySelectorAll('.tts-i'), function(b){
      b.addEventListener('click', function(){ startAt(+b.getAttribute('data-i')); });
    });
  }

  function showNow(item){
    var u = item.unit;
    elNow.textContent = (u.num ? u.num + ' · ' : '') + (u.title || '30 seconds');
    if(u !== lastUnit){
      lastUnit = u;
      Array.prototype.forEach.call(elList.querySelectorAll('.tts-i'), function(b, i){
        b.classList.toggle('on', units[i] === u);
      });
      try{ u.el.scrollIntoView({block:'start', behavior:'smooth'}); }catch(e){}
    }
  }

  /* ---- speaking ------------------------------------------------------ */

  function keepAlive(){
    clearTimeout(keep);
    keep = setTimeout(function(){
      if(!synth.speaking) return;
      synth.pause();
      synth.resume();
      keepAlive();
    }, 9000);
  }

  /* The rate and the voice are baked into an utterance when it is created,
     so changing either mid-sentence does nothing to the sound you are
     hearing -- it only affects the next block. Every utterance therefore
     carries a generation number. A stale one, whose audio was cancelled to
     make way for a replacement, is recognised and ignored rather than
     advancing the queue. */
  function speakItem(item, from){
    var myGen = ++gen;
    cur = item;
    offset = from || 0;
    curIndex = offset;
    var text = item.full.slice(offset);
    if(!text){ speakNext(); return; }
    var u = new SpeechSynthesisUtterance(text);
    u.rate = rate;
    if(voice) u.voice = voice;
    u.onboundary = function(ev){
      if(ev.name && ev.name !== 'word') return;
      curIndex = offset + ev.charIndex;
      if(item.markable) mark(item.els, curIndex, ev.charLength || 0);
    };
    u.onend = function(){ if(stopped || myGen !== gen) return; speakNext(); };
    u.onerror = function(){ if(stopped || myGen !== gen) return; speakNext(); };
    synth.speak(u);
    keepAlive();
  }

  function speakNext(){
    if(stopped) return;
    if(qi + 1 >= queue.length){ finish(); return; }
    qi++;
    var item = queue[qi];
    showNow(item);
    speakItem(item, 0);
  }

  /* Re-speak what is left of the current block with the new setting, from
     the word being read rather than from the top of the paragraph. A speed
     change that jumped back to the start of the sentence would make the
     reader hear the same words twice. */
  function restartCurrent(){
    if(stopped || !cur) return;
    var wasPaused = !playing;
    var item = cur;
    var from = curIndex;
    gen++;                       /* retire the utterance we are cancelling */
    try{ synth.cancel(); }catch(e){}
    clearMark();
    speakItem(item, from);
    if(wasPaused){
      synth.pause();
      playing = false;
      setPlay();
    }
  }

  function startAt(unitIndex){
    var target = -1;
    for(var i = 0; i < queue.length; i++){
      if(queue[i].unit === units[unitIndex]){ target = i; break; }
    }
    if(target < 0) return;
    synth.cancel();
    clearTimeout(keep);
    clearMark();
    qi = target - 1;
    stopped = false;
    playing = true;
    setPlay();
    speakNext();
  }

  function finish(){
    playing = false;
    stopped = true;
    clearTimeout(keep);
    setPlay();
  }

  function stop(){
    stopped = true;
    playing = false;
    clearTimeout(keep);
    try{ synth.cancel(); }catch(e){}
    clearMark();
    lastUnit = null;
    setPlay();
  }

  function setPlay(){
    if(elPlay) elPlay.textContent = playing ? 'Pause' : 'Play';
    if(elPlay) elPlay.setAttribute('aria-pressed', playing ? 'true' : 'false');
  }

  /* ---- voices -------------------------------------------------------- */

  /* Which voices exist is a property of the device, not of this page: a
     phone and a laptop ship completely different sets, and the list can
     change when an OS update adds a language pack. So the panel shows what
     the device actually has and says how many, rather than promising a
     voice that will not be there.

     The order is a judgement, not a fact. A Canadian account wants en-GB
     first; an Indian accent is the next best fit for the night shift; en-US
     last. Everything else follows, alphabetically. */
  function voiceRank(v){
    if(/^en-GB/i.test(v.lang)) return 0;
    if(/^en-IN/i.test(v.lang)) return 1;
    if(/^en/i.test(v.lang)) return 2;
    return 3;
  }

  function fillVoices(){
    if(!elVoice) return;
    var all = synth.getVoices() || [];
    if(elVoiceNote){
      elVoiceNote.textContent = all.length
        ? all.length + (all.length === 1 ? ' voice on this device'
                                          : ' voices on this device')
        : 'No voices found — this browser has no speech engine installed.';
    }
    if(!all.length){
      elVoice.innerHTML = '';
      elVoice.disabled = true;
      return;
    }
    elVoice.disabled = false;
    var sorted = all.slice().sort(function(a, b){
      var ra = voiceRank(a), rb = voiceRank(b);
      if(ra !== rb) return ra - rb;
      return (a.name || '').localeCompare(b.name || '');
    });
    var sig = sorted.map(function(v){ return v.voiceURI; }).join('|');
    if(elVoice.getAttribute('data-sig') === sig) return;
    elVoice.setAttribute('data-sig', sig);
    elVoice.innerHTML = sorted.map(function(v){
      return '<option value="' + esc(v.voiceURI) + '">'
           + esc(v.name) + ' — ' + esc(v.lang) + '</option>';
    }).join('');
    /* Keep the current pick if it is still on offer. */
    var keep = voice && voice.voiceURI;
    voice = null;
    for(var i = 0; i < sorted.length; i++){
      if(sorted[i].voiceURI === keep){ voice = sorted[i]; break; }
    }
    if(!voice) voice = sorted[0];
    elVoice.value = voice.voiceURI;
  }

  if(elVoice) elVoice.addEventListener('change', function(){
    var all = synth.getVoices() || [];
    for(var i = 0; i < all.length; i++){
      if(all[i].voiceURI === elVoice.value){
        if(all[i] !== voice){
          voice = all[i];
          /* Same reason as the rate: the voice is fixed when the utterance
             is created, so it has to be restarted to be heard. */
          restartCurrent();
        }
        return;
      }
    }
  });

  if(synth.addEventListener) synth.addEventListener('voiceschanged', fillVoices);
  fillVoices();

  /* ---- controls ------------------------------------------------------ */

  if(elPlay) elPlay.addEventListener('click', function(){
    if(playing){
      synth.pause();
      playing = false;
      setPlay();
      return;
    }
    if(stopped){
      if(!units.length) return;
      units = unitsOf();
      buildQueue();
      buildList();
      startAt(0);
      return;
    }
    synth.resume();
    playing = true;
    setPlay();
  });

  if(elStop) elStop.addEventListener('click', stop);

  if(elBack) elBack.addEventListener('click', function(){
    if(!cur) return;
    var idx = units.indexOf(cur.unit);
    if(idx > 0) startAt(idx - 1);
  });

  if(elClose) elClose.addEventListener('click', function(){ dlg.close(); });

  /* Backdrop click closes, the way the Index does. */
  dlg.addEventListener('click', function(e){
    if(e.target.closest('a')) return;
    if(e.target === dlg) dlg.close();
  });

  if(elRate){
    Array.prototype.forEach.call(elRate.querySelectorAll('button'), function(b){
      b.addEventListener('click', function(){
        var r = parseFloat(b.getAttribute('data-rate')) || 1;
        if(r === rate) return;
        rate = r;
        Array.prototype.forEach.call(elRate.querySelectorAll('button'), function(o){
          o.classList.toggle('on', o === b);
        });
        /* The rate is baked into the utterance already playing, so the
           sound would not change until the next block. Restart from the
           current word so the change is heard immediately. */
        restartCurrent();
      });
    });
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('[data-tts-open]'),
    function(b){
      b.addEventListener('click', function(){
        if(dlg.open) return;
        units = unitsOf();
        buildQueue();
        buildList();
        dlg.showModal();
      });
    });

  /* Opening the panel must not leave the phone's sheet half-drawn. */
  /* Closing the panel stops the reading. This has to live here rather than
     on the close button, because Escape fires `close` without touching the
     button -- so a panel dismissed with the keyboard used to keep talking
     with nothing on screen to stop it. */
  dlg.addEventListener('close', function(){ stop(); });

  /* Leaving the page for good stops it too. Backgrounding the tab does
     not fire this, which is what lets it keep reading while you do
     something else. */
  window.addEventListener('pagehide', function(){ stop(); });
})();
