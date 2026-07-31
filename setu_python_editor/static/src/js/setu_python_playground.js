/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { ensureJQuery } from "@web/core/ensure_jquery";

const { Component,onMounted, onWillStart,onWillDestroy, useState, useEffect,useRef } = owl;

export class setu_python_playground extends Component {
    setup() {
        super.setup();
        var self = this
        this.orm = useService("orm");
        this.action = useService("action");


        onWillStart(async () => {
            await ensureJQuery();
        });
        onMounted(async ()=> {
            $('.loader_code').removeClass('loader_code_hide');
            const res =   this.orm.call(
                'setu.python.editor',
                'get_code',
                [[this.props.action.context.active_id]],
            );
            res.then(async function (result) {
                self.self  = result['self']
                self.code  = result['code']
                self.editor_output  = result['output']
                self.editor_type  = result['editor_type']
                await self.onCreateEditor();
                await self.resizer();
                $(('.box-title-name')).html(result['name']);
                $('.loader_code').fadeOut('slow');
                $('.loader_code').addClass('loader_code_hide');
            })
            $('.setu_py_editor_playground').keydown(function(event){
                    if(event.keyCode == 116) {
                      event.preventDefault();
                      self.onEvaluatePython()
                      return false;
                    }
                    if(event.keyCode == 122) {
                        $('#icon_fullscreen').trigger('click');
                        self.onFullScreenEditor();
                    }``
                  });

                window.onresize = function(event) {
                    if (window.innerWidth <= 768) { // If media query matches
                            $('.resizable-x').removeClass('resizable-x').addClass('resizable-y').find('.div0')
                            $('.resizer-x').removeClass('resizer-x').addClass('resizer-y')
                            $('.fa-mobile').addClass('rotate-90')
                      }
                      else{
                            if(self.editor_type == 'python'){
                                $('.resizable-y').removeClass('resizable-y').addClass('resizable-x').find('.div0')
                                $('.resizer-y').removeClass('resizer-y').addClass('resizer-x')
                                $('.fa-mobile').removeClass('rotate-90');
                            }
                      }
                };
        });
    }
    onCreateEditor(){
        this.editor = CodeMirror.fromTextArea(
            document.getElementById("code"), {
                lineNumbers: true,
                gutter: true,
                lineWrapping: true,
                mode: {
                    name: "python",
                    version: 3,
                    singleLineStringErrors: false,
                },
                theme: "dracula",
                indentUnit: 4,
                matchBrackets: true,
                continueLineComment: true,
                extraKeys: {
                    "Ctrl-Space": "autocomplete",
                    'Ctrl-/': 'toggleComment',
                    "F11": function(cm) {
                        cm.setOption("fullScreen", !cm.getOption("fullScreen"));
                        },
                    "Esc": function(cm) {
                            if (cm.getOption("fullScreen")) cm.setOption("fullScreen", false);
                        }
                },
                foldGutter: true,
                gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
            }
        );
        this.editor.setValue(this.code || '');


        // find the output element
        this.output = CodeMirror.fromTextArea(
            document.getElementById("output"), {
                theme: "dracula",
                lineNumbers: false,
                mode: 'simple',
                indentUnit: 4,
                matchBrackets: true,
                lineWrapping: true,
                continueLineComment: true,
                readOnly: true,
            }
        );
        if(this.editor_type == 'python'){
              $('.resizable-y').removeClass('resizable-y').addClass('resizable-x').find('.div0')
            $('.resizer-y').removeClass('resizer-y').addClass('resizer-x')
             $('.fa-mobile').removeClass('rotate-90');
             $('.fa-info-circle').parent().removeClass('d-none');
             $('.is_python').removeClass('d-none');
            this.output.setValue(this.editor_output  || '');
        }
        else{
            $('.resizable-x').removeClass('resizable-x').addClass('resizable-y').find('.div0')
            $('.resizer-x').removeClass('resizer-x').addClass('resizer-y')
           $('.fa-mobile').addClass('rotate-90')
             $('.is_psql').removeClass('d-none');
             $('.fa-info-circle').parent().addClass('d-none');
             $('.output_erea').html(this.editor_output);
             $('.output_erea').addClass('table-responsive')
                $('#output_ed').addClass('table table-light').css('overflow','auto')
                $('#output_ed').find('thead').addClass('position-sticky').css('top','0')
        }
        if (window.innerWidth <= 768) { // If media query matches
                $('.resizable-x').removeClass('resizable-x').addClass('resizable-y').find('.div0')
                $('.resizer-x').removeClass('resizer-x').addClass('resizer-y')
                $('.fa-mobile').addClass('rotate-90')
          }
          else{
                if(self.editor_type == 'python'){
                    $('.resizable-y').removeClass('resizable-y').addClass('resizable-x').find('.div0')
                    $('.resizer-y').removeClass('resizer-y').addClass('resizer-x')
                    $('.fa-mobile').removeClass('rotate-90');
                }
          }
    }
    onEvaluatePython (ev) {
//        $('.loader_code').removeClass('loader_code_hide');
//        $('.loader_code').fadeIn('fast');
        this.editor.setOption("fullScreen", false);
        document.getElementsByClassName("dn_toolbar")[0].parentElement.classList.add('position-relative');
        document.getElementById("icon_fullscreen").setAttribute("class",'fa fa-expand')
        var code = this.editor.getValue();
        var result = this.output.getValue();
        var self = this
        const res =  this.orm.call(
            'setu.python.editor',
            'execute_code',
            [[this.self],[code,result]],
        );
        res.then(function (result) {
            if(self.editor_type == 'python'){
                self.output.setValue(result || '')
            }
            else{
                $('.output_erea').html('');
                $('.output_erea').html(result);
                $('.output_erea').addClass('table-responsive')
                $('#output_ed').addClass('table table-light').css('overflow','auto')
                $('#editor_right').find('thead').addClass('position-sticky').css('top','0')
                $('#editor_right').css('background','#FFF')
//            setTimeout(function () {
//                $('.loader_code').fadeOut('slow');
//                $('.loader_code').addClass('loader_code_hide');
//            },300)
            }
        })

    }
    onRotatePlayground(ev){
        if($('.fa-mobile').hasClass('rotate-90'))
        {
            $('.resizable-y').removeClass('resizable-y').addClass('resizable-x').find('.div0').css('flex','50%')
            $('.resizer-y').removeClass('resizer-y').addClass('resizer-x')
             $('.fa-mobile').removeClass('rotate-90');
             $('.div1').css('flex','50%')

        }
        else{
           $('.fa-mobile').addClass('rotate-90')
            $('.resizable-x').removeClass('resizable-x').addClass('resizable-y').find('.div0').css('flex','50%')
            $('.resizer-x').removeClass('resizer-x').addClass('resizer-y')
             $('.div1').css('flex','50%')


        }
    }
    onCopyToClipboard(ev){
        $('.setu_toast').remove();
        const tempInput = document.createElement("textarea");
        tempInput.style = "position: absolute; left: -1000px; top: -1000px";
        tempInput.value = this.editor.getValue();
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand("copy");
        document.body.removeChild(tempInput);
        $('body').append(" <div class='toast setu_toast position-fixed bottom-0 end-0 m-4 hide'><div class='toast-header'><strong class='me-auto'>Helping Hand</strong></div><div class='toast-body'><p>Copied Successfully</p></div></div>")
        $('.setu_toast').fadeIn('slow')
        function quickadd() {
			setTimeout(function () {
			    $('.setu_toast').fadeOut('slow')
			}, 2000);
		}
		quickadd();
    }
    onBack(ev){
        var self = this;
       window.history.back();
    }
    onFullScreenEditor(ev){
       if(! this.editor.getOption("fullScreen"))
       {
            $('.dn_toolbar').removeClass('d-none')
            document.getElementById("icon_fullscreen").setAttribute("class",'fa fa-arrows-alt')
            document.getElementsByClassName("dn_toolbar")[0].parentElement.classList.remove('position-relative')
        }
        else{
            $('.dn_toolbar').addClass('d-none')
            document.getElementById("icon_fullscreen").setAttribute("class",'fa fa-expand')
            document.getElementsByClassName("dn_toolbar")[0].parentElement.classList.add('position-relative')
        }
        this.editor.setOption("fullScreen", !this.editor.getOption("fullScreen"));
    }
    onOpenHelp(ev){
        this.editor.setOption("fullScreen", false);
        document.getElementsByClassName("dn_toolbar")[0].parentElement.classList.add('position-relative');
        document.getElementById("icon_fullscreen").setAttribute("class",'fa fa-expand')
       var info = `=========================================
            Use Full Shortcuts
=========================================

Ctrl-F / Cmd-F
    Start searching
Ctrl-G / Cmd-G
    Find next
Shift-Ctrl-G / Shift-Cmd-G
    Find previous
Shift-Ctrl-F / Cmd-Option-F
    Replace
Shift-Ctrl-R / Shift-Cmd-Option-F
    Replace all
Alt-G
    Jump to line

=========================================
                How To Use
=========================================

num = 2
ans = ''
if (num % 2) == 0:
   ans = "{0} is Even".format(num)
else:
   ans = "{0} is Odd".format(num)

result = ans  # result variable always contains your output

Output : 2 is Even

=========================================
Copyright (c) 2022 - 2023 - Version : 0.2,
        Made with ❤ by HB Team
=========================================
`
       this.output.setValue(info)
    }
    resizer(){
        const resizerx =  document.querySelector(".resizer-x") || document.querySelector(".resizer-y");
        if (resizerx == null){
             resizerx = document.querySelector(".resizer-y");
        }

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
    }
}

setu_python_playground.template = 'SetuPythonPlayGround';



registry.category('actions').add('setu_python_playground', setu_python_playground);
