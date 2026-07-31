(function () {
  "use strict";

  // horizontal direction

 (function resizableX() {
    const resizerx = document.querySelector(".resizer-x");

    resizerx.addEventListener("mousedown", onmousedownx);
    resizerx.addEventListener("touchstart", ontouchstartx);

    // for mobile
    function ontouchstartx(e) {
      e.preventDefault();
      if ($(resizerx).hasClass('resizer-x')){
          resizerx.addEventListener("touchmove", ontouchmovex);
          resizerx.addEventListener("touchend", ontouchendx);
      }
      else{
          resizerx.addEventListener("touchmove", ontouchmove);
          resizerx.addEventListener("touchend", ontouchend);
      }
    }
    function ontouchmovex(e) {
      e.preventDefault();
      const clientX = e.touches[0].clientX;
      const deltaX = clientX - (resizerx._clientX || clientX);
      resizerx._clientX = clientX;
      const l = resizerx.previousElementSibling;
      const r = resizerx.nextElementSibling;
      // LEFT
      if (deltaX < 0) {
        
        const w = Math.round(parseInt(getComputedStyle(l).width) + deltaX);
        l.style.flex = `0 ${w < 10 ? 0 : w}px`;
        r.style.flex = "1 0";
      }
      // RIGHT
      if (deltaX > 0) {
        
        const w = Math.round(parseInt(getComputedStyle(r).width) - deltaX);
        r.style.flex = `0 ${w < 10 ? 0 : w}px`;
        l.style.flex = "1 0";
      }
    }
    function ontouchendx(e) {
      e.preventDefault();
      if ($(resizerx).hasClass('resizer-x')){
          resizerx.removeEventListener("touchmove", ontouchmovex);
          resizerx.removeEventListener("touchend", ontouchendx);
      }
      else{
            resizerx.removeEventListener("touchmove", ontouchmove);
          resizerx.removeEventListener("touchend", ontouchend);
      }
      delete e._clientX;
    }

    // for desktop
    function onmousedownx(e) {
        
      e.preventDefault();
      if ($(resizerx).hasClass('resizer-x')){
          document.addEventListener("mousemove", onmousemovex);
          document.addEventListener("mouseup", onmouseupx);
      }
      else{
          document.addEventListener("mousemove", onmousemove);
          document.addEventListener("mouseup", onmouseup);
      }
    }
    function onmousemovex(e) {
      e.preventDefault();
      const clientX = e.clientX;
      const deltaX = clientX - (resizerx._clientX || clientX);
      resizerx._clientX = clientX;
      const l = resizerx.previousElementSibling;
      const r = resizerx.nextElementSibling;
      // LEFT
      if (deltaX < 0) {
        const w = Math.round(parseInt(getComputedStyle(l).width) + deltaX);
        l.style.flex = `0 ${w < 10 ? 0 : w}px`;
        r.style.flex = "1 0";
      }
      // RIGHT
      if (deltaX > 0) {
        const w = Math.round(parseInt(getComputedStyle(r).width) - deltaX);
        r.style.flex = `0 ${w < 10 ? 0 : w}px`;
        l.style.flex = "1 0";
      }
    }
    function onmouseupx(e) {
      e.preventDefault();
      if ($(resizerx).hasClass('resizer-x')){
          document.removeEventListener("mousemove", onmousemovex);
          document.removeEventListener("mouseup", onmouseupx);
      }
      else{
          document.removeEventListener("mousemove", onmousemove);
          document.removeEventListener("mouseup", onmouseup);
      }
      delete e._clientX;
    }


    function ontouchstart(e) {
      e.preventDefault();
      resizerx.addEventListener("touchmove", ontouchmove);
      resizerx.addEventListener("touchend", ontouchend);
    }
    function ontouchmove(e) {
      e.preventDefault();
      const clientY = e.touches[0].clientY;
      const deltaY = clientY - (resizerx._clientY || clientY);
      resizerx._clientY = clientY;
      const t = resizerx.previousElementSibling;
      const b = resizerx.nextElementSibling;
      // UP
      if (deltaY < 0) {
        const h = Math.round(parseInt(getComputedStyle(t).height) + deltaY);
        t.style.flex = `0 ${h < 10 ? 0 : h}px`;
        b.style.flex = "1 0";
      }
      // DOWN
      if (deltaY > 0) {
        const h = Math.round(parseInt(getComputedStyle(b).height) - deltaY);
        b.style.flex = `0 ${h < 10 ? 0 : h}px`;
        t.style.flex = "1 0";
      }
    }
    function ontouchend(e) {
      e.preventDefault();
      resizerx.removeEventListener("touchmove", ontouchmove);
      resizerx.removeEventListener("touchend", ontouchend);
      delete e._clientY;
    }

    // for desktop
    function onmousedown(e) {
      e.preventDefault();
      document.addEventListener("mousemove", onmousemove);
      document.addEventListener("mouseup", onmouseup);
    }
    function onmousemove(e) {
      e.preventDefault();
      const clientY = e.clientY;
      const deltaY = clientY - (resizerx._clientY || clientY);
      resizerx._clientY = clientY;
      const t = resizerx.previousElementSibling;
      const b = resizerx.nextElementSibling;
      // UP
      if (deltaY < 0) {
        
        const h = Math.round(parseInt(getComputedStyle(t).height) + deltaY);
        t.style.flex = `0 ${h < 10 ? 0 : h}px`;
        b.style.flex = "1 0";
      }
      // DOWN
      if (deltaY > 0) {
        
        const h = Math.round(parseInt(getComputedStyle(b).height) - deltaY);
        b.style.flex = `0 ${h < 10 ? 0 : h}px`;
        t.style.flex = "1 0";
      }
    }
    function onmouseup(e) {
      e.preventDefault();
      document.removeEventListener("mousemove", onmousemove);
      document.removeEventListener("mouseup", onmouseup);
      delete e._clientY;
    }


  })();

})();
