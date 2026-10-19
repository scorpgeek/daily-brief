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
  var elClose = document.getElementById('ttsClose');

  var rate = 1, voice = null, units = [], queue = [], qi = -1;
  var cur = null, keep = null, playing = false, stopped = true;
  var markEl = null, lastUnit = null;

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
     the item, rather than twice. */
  var BLOCKS = 'p,li,h4,h5,dt,dd,blockquote,table';

  function blocksOf(el){
    var out = [];
    Array.prototype.forEach.call(el.querySelectorAll(BLOCKS), function(n){
      if(n.querySelector(BLOCKS)) return;
      out.push(n);
    });
    return out;
  }

  /* The text and the text nodes it came from. The engine reports word
     offsets into the string it was given, so the string has to be built the
     same way when speaking and when highlighting. */
  function walk(block){
    var walker = document.createTreeWalker(block, 4);
    var parts = [], text = '', n;
    while((n = walker.nextNode())){
      var t = (n.nodeValue || '').replace(/\s+/g, ' ');
      if(!t) continue;
      parts.push({node:n, text:t, start:text.length});
      text += t;
    }
    return {parts:parts, text:text};
  }

  function textOf(block){
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
    return walk(block).text;
  }

  function buildQueue(){
    queue = [];
    units.forEach(function(u){
      blocksOf(u.el).forEach(function(bl){
        var t = textOf(bl);
        if(t && t.length) queue.push({unit:u, block:bl, text:t});
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

  function mark(block, start, len){
    clearMark();
    if(!len) return;
    var w = walk(block);
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

  function speakNext(){
    if(stopped) return;
    if(qi + 1 >= queue.length){ finish(); return; }
    qi++;
    var item = queue[qi];
    cur = item;
    showNow(item);
    var u = new SpeechSynthesisUtterance(item.text);
    u.rate = rate;
    if(voice) u.voice = voice;
    u.onboundary = function(ev){
      if(ev.name && ev.name !== 'word') return;
      mark(item.block, ev.charIndex, ev.charLength || 0);
    };
    u.onend = function(){ if(!stopped) speakNext(); };
    u.onerror = function(){ if(!stopped) speakNext(); };
    synth.speak(u);
    keepAlive();
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

  /* Voices load asynchronously in most browsers, so the list is filled now
     and again when it changes. A Canadian account wants en-GB; an Indian
     accent is the next best fit, and en-US last. */
  function fillVoices(){
    if(!elVoice) return;
    var all = synth.getVoices() || [];
    var eng = all.filter(function(v){ return /^en/i.test(v.lang); });
    if(!eng.length) return;
    eng.sort(function(a, b){
      var rank = function(v){
        if(/en-GB/i.test(v.lang)) return 0;
        if(/en-IN/i.test(v.lang)) return 1;
        if(/^en/i.test(v.lang)) return 2;
        return 3;
      };
      return rank(a) - rank(b);
    });
    if(elVoice.options.length === eng.length
       && elVoice.options.length
       && elVoice.options[0].value === eng[0].voiceURI) return;
    elVoice.innerHTML = eng.map(function(v){
      return '<option value="' + esc(v.voiceURI) + '">' + esc(v.name) + '</option>';
    }).join('');
    voice = eng[0];
    elVoice.value = voice.voiceURI;
    elVoice.addEventListener('change', function(){
      var pick = eng.filter(function(v){ return v.voiceURI === elVoice.value; })[0];
      if(pick) voice = pick;
    });
  }

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

  if(elClose) elClose.addEventListener('click', function(){
    stop();
    dlg.close();
  });

  dlg.addEventListener('click', function(e){
    if(e.target.closest('a')) return;
    if(e.target === dlg) stop();
  });

  if(elRate){
    Array.prototype.forEach.call(elRate.querySelectorAll('button'), function(b){
      b.addEventListener('click', function(){
        rate = parseFloat(b.getAttribute('data-rate')) || 1;
        Array.prototype.forEach.call(elRate.querySelectorAll('button'), function(o){
          o.classList.toggle('on', o === b);
        });
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
  dlg.addEventListener('close', function(){ clearMark(); });
})();
