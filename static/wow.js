/* Consultoría Clínica Chile · animaciones e interacciones del sitio.
   Todo es mejora progresiva: sin este archivo, o con «reducir movimiento», el sitio se ve completo y fijo.
   Lo que solo debe ocultarse cuando este script corre va bajo la clase .wow (se agrega aquí).
   Para ver los pop-ups sin esperar: ?ver=popup o ?ver=chat en la URL. */
(function () {
  'use strict';
  var d = document, w = window, raiz = d.documentElement;
  var quieto = w.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var conCursor = w.matchMedia('(hover: hover) and (pointer: fine)').matches;
  var ver = (/[?&]ver=([a-z]+)/.exec(location.search) || [])[1] || '';
  var DIA = 86400000;

  function leer(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function guardar(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function sesion(k, v) {
    try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) {}
    return null;
  }
  function reciente(k, dias) { var t = parseInt(leer(k), 10); return !!t && Date.now() - t < dias * DIA; }
  function medir(nombre, datos) { if (typeof fbq !== 'undefined') fbq('trackCustom', nombre, datos || {}); }
  function limitar(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function avisoCookiesVisible() { var b = d.getElementById('cookie-banner'); return !!b && !b.hidden; }

  raiz.classList.add('wow');

  /* ---------- Formularios que abren WhatsApp ---------- */
  function abrirWhatsApp(base, texto) { w.open(base + '?text=' + encodeURIComponent(texto), '_blank', 'noopener'); sesion('ccc-wa', '1'); }
  // «Cuéntanos tu caso» (portada y pop-up): arma el texto para Andrea con el tipo y la comuna.
  d.querySelectorAll('form[data-caso]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var texto = form.dataset.texto, tipo = form.tipo.value, comuna = form.comuna.value.trim();
      if (tipo) texto += ' para ' + tipo;
      if (comuna) texto += (tipo ? ' en ' : ', en ') + comuna;
      abrirWhatsApp(form.dataset.whatsapp, texto + '.');
      if (w.cccLead) w.cccLead(form.dataset.caso || 'formulario-rs', 'rs');
    });
  });
  // «Revisar gratis» (marcas): el texto contiene «revisar mi marca», que activa el bot de marcas.
  d.querySelectorAll('form[data-revisar]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var marca = form.marca.value.trim();
      if (!marca) return;
      abrirWhatsApp(form.dataset.whatsapp, form.dataset.texto + ': ' + marca);
      if (w.cccLead) w.cccLead(form.dataset.revisar || 'revisar-marca', 'marcas');
    });
  });
  // Medición: de dónde vienen los clics al autotest (banner de la sección, pop-up o pie).
  d.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-autotest]');
    if (a) medir('ClicAutotest', { content_name: a.dataset.autotest, content_category: 'rs' });
  });
  // Medición: clic en «Pagar con tarjeta» (va al link corto de Mercado Pago).
  d.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-pago]');
    if (!a) return;
    sesion('ccc-wa', '1');   // ya está comprando: sin pop-ups
    if (typeof fbq !== 'undefined') fbq('track', 'InitiateCheckout', { content_name: a.dataset.pago, content_category: a.dataset.lineaPago || 'rs', value: Number(a.dataset.valor) || 0, currency: 'CLP' });
  });
  // Quien ya abrió WhatsApp no vuelve a ver pop-ups en esta visita.
  d.addEventListener('click', function (e) { if (e.target.closest('a[href*="wa.me"]')) sesion('ccc-wa', '1'); });

  /* ---------- Banner superior ---------- */
  var anuncio = d.getElementById('anuncio');
  if (anuncio) {
    anuncio.querySelector('.anuncio-cerrar').addEventListener('click', function () {
      guardar('ccc-anuncio', anuncio.dataset.anuncio);
      anuncio.classList.add('saliendo');
      setTimeout(function () { anuncio.hidden = true; }, quieto ? 0 : 280);
    });
  }

  /* ---------- Scroll: barra de progreso, menú compacto y líneas de tiempo ---------- */
  var barra = d.querySelector('.progreso i');
  var nav = d.querySelector('.nav');
  var lineas = [].slice.call(d.querySelectorAll('[data-linea-tiempo]'));
  function alScroll() {
    var y = w.scrollY || 0, alto = raiz.scrollHeight - w.innerHeight;
    if (barra) barra.style.transform = 'scaleX(' + (alto > 0 ? limitar(y / alto, 0, 1) : 0) + ')';
    if (nav) nav.classList.toggle('compacta', y > 60);
    lineas.forEach(function (ol) {
      var r = ol.getBoundingClientRect();
      var p = quieto ? 1 : limitar((w.innerHeight * 0.82 - r.top) / (r.height + w.innerHeight * 0.25), 0, 1);
      var pasos = ol.children, n = pasos.length;
      ol.style.setProperty('--avance', p.toFixed(3));
      for (var i = 0; i < n; i++) pasos[i].classList.toggle('activo', p >= (i + 0.35) / n);
    });
  }
  var pendiente = false;
  w.addEventListener('scroll', function () {
    if (pendiente) return;
    pendiente = true;
    requestAnimationFrame(function () { pendiente = false; alScroll(); });
  }, { passive: true });
  w.addEventListener('resize', alScroll);
  alScroll();

  /* ---------- Conteo animado de cifras ---------- */
  var cifras = d.querySelectorAll('[data-contar]');
  if (cifras.length && !quieto && 'IntersectionObserver' in w) {
    var obsCifras = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (!en.isIntersecting) return;
        obsCifras.unobserve(en.target);
        var el = en.target, fin = parseInt(el.dataset.contar, 10), t0 = null, dur = 1500;
        function paso(t) {
          if (t0 === null) t0 = t;
          var k = limitar((t - t0) / dur, 0, 1), suave = 1 - Math.pow(1 - k, 3);
          el.textContent = Math.round(fin * suave).toLocaleString('es-CL');
          if (k < 1) requestAnimationFrame(paso);
        }
        el.textContent = '0';
        requestAnimationFrame(paso);
      });
    }, { threshold: 0.6 });
    cifras.forEach(function (el) { obsCifras.observe(el); });
  }

  /* ---------- Foco de luz e inclinación en tarjetas (solo con mouse) ---------- */
  if (conCursor) {
    d.querySelectorAll('.foco').forEach(function (el) {
      el.addEventListener('pointermove', function (e) {
        var r = el.getBoundingClientRect();
        el.style.setProperty('--fx', (e.clientX - r.left) + 'px');
        el.style.setProperty('--fy', (e.clientY - r.top) + 'px');
      });
    });
    if (!quieto) {
      d.querySelectorAll('[data-inclinar]').forEach(function (el) {
        el.addEventListener('pointermove', function (e) {
          var r = el.getBoundingClientRect();
          var dx = (e.clientX - r.left) / r.width - 0.5, dy = (e.clientY - r.top) / r.height - 0.5;
          var ang = Math.sqrt(dx * dx + dy * dy) * 9;
          el.style.rotate = (-dy).toFixed(3) + ' ' + dx.toFixed(3) + ' 0 ' + ang.toFixed(2) + 'deg';
        });
        el.addEventListener('pointerleave', function () { el.style.rotate = ''; });
      });
    }
  }

  /* ---------- Preguntas frecuentes: abrir y cerrar con animación ---------- */
  if (!quieto && Element.prototype.animate) {
    d.querySelectorAll('.faq details, .mk-faq details').forEach(function (det) {
      var sum = det.querySelector('summary'), anim = null;
      if (!sum) return;
      sum.addEventListener('click', function (e) {
        e.preventDefault();
        if (anim) anim.cancel();
        var abrir = !det.open, desde = det.offsetHeight, hasta;
        if (abrir) { det.open = true; hasta = det.offsetHeight; }
        else { det.open = false; hasta = det.offsetHeight; det.open = true; }
        det.style.overflow = 'hidden';
        det.classList.toggle('cerrando', !abrir);
        anim = det.animate({ height: [desde + 'px', hasta + 'px'] }, { duration: 280, easing: 'cubic-bezier(0.4, 0, 0.2, 1)' });
        anim.onfinish = anim.oncancel = function () {
          det.style.overflow = '';
          det.classList.remove('cerrando');
          if (!abrir) det.open = false;
          anim = null;
        };
      });
    });
  }

  /* ---------- Buscador de marcas: ejemplos que se escriben solos ---------- */
  d.querySelectorAll('input[data-escribir]').forEach(function (input) {
    if (quieto) return;
    var ejemplos = input.dataset.escribir.split('|'), original = input.placeholder;
    var i = 0, pos = 0, borrando = false, reloj = null, detenido = false;
    function tic() {
      if (detenido) return;
      var palabra = ejemplos[i];
      pos += borrando ? -1 : 1;
      input.placeholder = 'Ej.: ' + palabra.slice(0, pos) + (pos < palabra.length || borrando ? '|' : '');
      var espera = borrando ? 38 : 85;
      if (!borrando && pos === palabra.length) { borrando = true; espera = 1500; }
      else if (borrando && pos === 0) { borrando = false; i = (i + 1) % ejemplos.length; espera = 350; }
      reloj = setTimeout(tic, espera);
    }
    function parar() { detenido = true; clearTimeout(reloj); input.placeholder = original; }
    input.addEventListener('focus', parar);
    reloj = setTimeout(tic, 1800);
  });

  /* ---------- Fondo animado (WebGL). Si no hay WebGL, queda el degradado de CSS ---------- */
  var VERT = 'attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}';
  var FRAG = [
    '#ifdef GL_FRAGMENT_PRECISION_HIGH', 'precision highp float;', '#else', 'precision mediump float;', '#endif',
    'uniform vec2 r;uniform float t;uniform vec2 m;uniform float k;',
    'float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}',
    'float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);',
    'return mix(mix(h(i),h(i+vec2(1.,0.)),f.x),mix(h(i+vec2(0.,1.)),h(i+vec2(1.,1.)),f.x),f.y);}',
    'float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*n(p);p=p*2.03+vec2(17.3,9.1);a*=.5;}return v;}',
    'void main(){',
    'vec2 uv=gl_FragCoord.xy/r;vec2 p=uv;p.x*=r.x/r.y;',
    'float tt=t*.055;',
    'vec2 q=vec2(fbm(p*1.15+vec2(0.,tt)),fbm(p*1.15+vec2(5.2,-tt*1.3)));',
    'vec2 s=vec2(fbm(p*1.5+2.4*q+vec2(1.7,9.2)+tt*.8),fbm(p*1.5+2.4*q+vec2(8.3,2.8)-tt*.6));',
    'float f=fbm(p*1.25+3.*s+(m-.5)*.35);',
    // Oscuro: marino profundo → marino → azul → celeste
    'vec3 o=mix(vec3(.024,.075,.16),vec3(.071,.216,.412),smoothstep(.2,.62,f));',
    'o=mix(o,vec3(.176,.482,.796),smoothstep(.36,.78,f)*min(1.,length(q)*1.15));',
    'o=mix(o,vec3(.494,.784,.89),smoothstep(.56,.95,f)*s.y*s.y*1.05);',
    'o*=.74+.26*smoothstep(0.,1.,uv.x*.55+uv.y*.6);',
    // Claro: blanco → celeste muy suave → azul muy suave; se funde a blanco hacia abajo
    'vec3 c=mix(vec3(1.),vec3(.902,.937,.976),smoothstep(.25,.7,f));',
    'c=mix(c,vec3(.74,.87,.95),smoothstep(.45,.9,f)*.8*length(q));',
    'c=mix(c,vec3(.6,.78,.93),smoothstep(.62,1.,f)*s.y*s.y*.7);',
    'c=mix(vec3(1.),c,smoothstep(0.,.45,uv.y));',
    'vec3 col=mix(o,c,k);',
    'col+=(h(gl_FragCoord.xy+fract(t))-.5)*mix(.016,.008,k);',
    'gl_FragColor=vec4(col,1.);}'
  ].join('\n');

  function fondoVivo(canvas) {
    if (quieto || (navigator.connection && navigator.connection.saveData)) return;
    var gl;
    try { gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' }); } catch (e) {}
    if (!gl) return;
    function sombra(tipo, codigo) {
      var s = gl.createShader(tipo);
      gl.shaderSource(s, codigo); gl.compileShader(s);
      return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
    }
    var v = sombra(gl.VERTEX_SHADER, VERT), f = sombra(gl.FRAGMENT_SHADER, FRAG);
    if (!v || !f) return;
    var prog = gl.createProgram();
    gl.attachShader(prog, v); gl.attachShader(prog, f); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var a = gl.getAttribLocation(prog, 'a');
    gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    var uR = gl.getUniformLocation(prog, 'r'), uT = gl.getUniformLocation(prog, 't');
    var uM = gl.getUniformLocation(prog, 'm'), uK = gl.getUniformLocation(prog, 'k');
    gl.uniform1f(uK, canvas.dataset.fondo === 'claro' ? 1 : 0);

    var mx = 0.5, my = 0.5, tx = 0.5, ty = 0.5, visible = true, apagado = false, ultimo = 0, cuadro = null, inicio = performance.now();
    function medirLienzo() {
      // Se dibuja a baja resolución (máx. 720 px de ancho) y el navegador lo estira: es un fondo difuso.
      var escala = Math.min(0.5, 720 / Math.max(1, canvas.clientWidth));
      var cw = Math.max(2, Math.round(canvas.clientWidth * escala)), ch = Math.max(2, Math.round(canvas.clientHeight * escala));
      if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; gl.viewport(0, 0, cw, ch); }
      gl.uniform2f(uR, cw, ch);
    }
    function dibujar(ahora) {
      cuadro = null;
      if (!visible || d.hidden || apagado) return;
      cuadro = requestAnimationFrame(dibujar);
      if (ahora - ultimo < 33) return;   // ~30 cuadros por segundo
      ultimo = ahora;
      mx += (tx - mx) * 0.04; my += (ty - my) * 0.04;
      gl.uniform1f(uT, (ahora - inicio) / 1000);
      gl.uniform2f(uM, mx, my);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    function arrancar() { if (!cuadro && visible && !d.hidden && !apagado) cuadro = requestAnimationFrame(dibujar); }
    canvas.addEventListener('pausar', function () { apagado = true; });   // cuando el video de fondo ya se ve
    medirLienzo();
    w.addEventListener('resize', medirLienzo);
    if (conCursor) {
      w.addEventListener('pointermove', function (e) { tx = e.clientX / w.innerWidth; ty = 1 - e.clientY / w.innerHeight; }, { passive: true });
    }
    if ('IntersectionObserver' in w) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; arrancar(); }).observe(canvas);
    }
    d.addEventListener('visibilitychange', arrancar);
    canvas.addEventListener('webglcontextlost', function (e) { e.preventDefault(); visible = false; canvas.classList.remove('listo'); });
    arrancar();
    requestAnimationFrame(function () { canvas.classList.add('listo'); });
  }
  d.querySelectorAll('canvas[data-fondo]').forEach(fondoVivo);

  /* ---------- Videos de fondo: llegan después de la página y solo con buena conexión ---------- */
  var conexion = navigator.connection || {};
  var conexionLenta = !!conexion.saveData || /(^|-)2g$|^3g$/.test(conexion.effectiveType || '');
  d.querySelectorAll('video[data-video]').forEach(function (v) {
    if (quieto || conexionLenta || !('IntersectionObserver' in w)) return;   // queda el fondo animado
    var seccion = v.parentElement, pedido = false;
    function cargar() {
      if (pedido) return;
      pedido = true;
      v.addEventListener('playing', function () {
        v.classList.add('listo');
        seccion.classList.add('con-video');
        var lienzo = seccion.querySelector('canvas[data-fondo]');
        if (lienzo) setTimeout(function () { lienzo.dispatchEvent(new Event('pausar')); }, 1800);
      }, { once: true });
      v.src = v.dataset.video;
      var p = v.play();
      if (p && p.catch) p.catch(function () {});   // ahorro de batería: no se reproduce y queda el fondo animado
    }
    new IntersectionObserver(function (en) {
      var cerca = en[0].isIntersecting;
      if (cerca && !pedido) { if (d.readyState === 'complete') cargar(); else w.addEventListener('load', cargar); }
      else if (pedido) { if (cerca) { var p = v.play(); if (p && p.catch) p.catch(function () {}); } else v.pause(); }
    }, { rootMargin: '300px' }).observe(v);
  });

  /* ---------- Globo de chat junto al botón de WhatsApp ---------- */
  var teaser = d.getElementById('teaser');
  var modal = d.querySelector('[data-modal-salida]');
  var modalAbierto = false;
  function cerrarTeaser(recordar) {
    if (!teaser || teaser.hidden) return;
    teaser.classList.remove('abierto');
    setTimeout(function () { teaser.hidden = true; }, quieto ? 0 : 260);
    if (recordar) guardar('ccc-teaser-no', String(Date.now()));
  }
  function abrirTeaser() {
    if (!teaser || !teaser.hidden || modalAbierto) return;
    sesion('ccc-teaser', '1');
    teaser.hidden = false;
    requestAnimationFrame(function () { requestAnimationFrame(function () { teaser.classList.add('abierto'); }); });
    setTimeout(function () { teaser.classList.add('listo'); }, quieto ? 0 : 1300);
    // Si nadie lo toca, se guarda solo a los 20 segundos para no tapar el contenido.
    var tocado = false;
    teaser.addEventListener('pointerenter', function () { tocado = true; });
    teaser.addEventListener('focusin', function () { tocado = true; });
    if (ver !== 'chat') setTimeout(function () { if (!tocado) cerrarTeaser(false); }, 20000);
    medir('GloboChat');
  }
  if (teaser) {
    teaser.querySelector('.teaser-cerrar').addEventListener('click', function () { cerrarTeaser(true); });
    teaser.addEventListener('click', function (e) { if (e.target.closest('a')) cerrarTeaser(false); });
    var puedeTeaser = ver === 'chat' || (!sesion('ccc-teaser') && !sesion('ccc-wa') && !reciente('ccc-teaser-no', 3));
    if (puedeTeaser) {
      var listoTeaser = false;
      var intentar = function () {
        if (listoTeaser || !teaser.hidden) return;
        if (avisoCookiesVisible()) { setTimeout(intentar, 3000); return; }   // primero se resuelve el aviso de cookies
        listoTeaser = true;
        abrirTeaser();
      };
      setTimeout(intentar, ver === 'chat' ? 400 : 14000);
      w.addEventListener('scroll', function alBajar() {
        if ((w.scrollY || 0) > (raiz.scrollHeight - w.innerHeight) * 0.35) { w.removeEventListener('scroll', alBajar); intentar(); }
      }, { passive: true });
    }
  }

  /* ---------- Pop-up de salida ---------- */
  if (modal) {
    var caja = modal.querySelector('.modal-caja'), antes = null, llegada = Date.now();
    var cerrarModal = function () {
      if (!modalAbierto) return;
      modalAbierto = false;
      modal.classList.remove('abierto');
      d.body.classList.remove('con-modal');
      setTimeout(function () { modal.hidden = true; }, quieto ? 0 : 260);
      if (antes && antes.focus) antes.focus();
    };
    var abrirModal = function (forzar) {
      if (modalAbierto) return;
      if (!forzar) {
        if (reciente('ccc-salida', 7) || sesion('ccc-wa') || avisoCookiesVisible()) return;
        if (Date.now() - llegada < 12000) return;
        if (/^(INPUT|SELECT|TEXTAREA)$/.test((d.activeElement || {}).tagName || '')) return;   // está escribiendo
      }
      guardar('ccc-salida', String(Date.now()));
      cerrarTeaser(false);
      antes = d.activeElement;
      modalAbierto = true;
      modal.hidden = false;
      d.body.classList.add('con-modal');
      requestAnimationFrame(function () { requestAnimationFrame(function () { modal.classList.add('abierto'); }); });
      var primero = caja.querySelector('select, input, a.btn');
      if (primero && conCursor) setTimeout(function () { primero.focus(); }, 120);
      medir('PopupSalida', { content_category: modal.dataset.modalSalida });
    };
    modal.addEventListener('click', function (e) { if (e.target.closest('[data-cerrar]')) cerrarModal(); });
    modal.addEventListener('submit', function () { setTimeout(cerrarModal, 50); });
    d.addEventListener('keydown', function (e) {
      if (!modalAbierto) return;
      if (e.key === 'Escape') { cerrarModal(); return; }
      if (e.key !== 'Tab') return;
      var foco = caja.querySelectorAll('button, select, input, a[href]');
      var primero = foco[0], ultimoFoco = foco[foco.length - 1];
      if (e.shiftKey && d.activeElement === primero) { e.preventDefault(); ultimoFoco.focus(); }
      else if (!e.shiftKey && d.activeElement === ultimoFoco) { e.preventDefault(); primero.focus(); }
    });
    if (ver === 'popup') setTimeout(function () { abrirModal(true); }, 500);
    else if (conCursor) {
      // Escritorio: el cursor sale por arriba de la página.
      d.addEventListener('mouseout', function (e) { if (!e.relatedTarget && e.clientY <= 0) abrirModal(false); });
    } else {
      // Móvil: 50 segundos en la página y más de la mitad recorrida.
      var revisar = function () {
        if (Date.now() - llegada > 50000 && (w.scrollY || 0) > (raiz.scrollHeight - w.innerHeight) * 0.5) {
          w.removeEventListener('scroll', revisar);
          abrirModal(false);
        }
      };
      w.addEventListener('scroll', revisar, { passive: true });
    }
  }
})();
