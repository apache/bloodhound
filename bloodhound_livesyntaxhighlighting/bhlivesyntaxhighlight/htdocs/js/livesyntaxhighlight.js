//Defining a class for livesyntaxhighlight related stuff.
livesyntaxhighlight = {
  twidth : "",
  theight : "",
  cmwidth : "",
  cmheight : "",
  editor : null,
  //Initializing function
  init : function () {
    twidth = $('#text').width();
    theight = $('#text').height();
    editor = CodeMirror.fromTextArea(document.getElementById("text"), {
        lineNumbers: true,
        matchBrackets: true,
        continueComments: "Enter",
        extraKeys: {"Ctrl-Q": "toggleComment"}
      });
    console.log($('#text').width() + ' '+ $('#text').height());
    livesyntaxhighlight.resizeCodeMirror();
    editor.refresh();
    $(window).resize(livesyntaxhighlight.resizeCodeMirror);
  },
  resizeCodeMirror : function (){
    console.log($('#text').width() + ' '+ $('#text').height());
    var spanwidth = $('.span12').width()/2 - 15;
    cmwidth = window.twidth;
    if ($('.span12').width() > 688 && document.getElementById('sidebyside').checked)
      cmwidth = spanwidth;
    else cmwidth = 2 * (spanwidth +15);
    cmheight = $('#text').height();
    // if(document.getElementById('preview'))
    //   cmheight = $('#preview').height();
    editor.setSize(cmwidth, cmheight);
    editor.refresh();
  }
};
// Invoked initially to initialize the editor
$(document).ready(function (){
  livesyntaxhighlight.init();
});
// To adjust the height of the editor
$("#editrows").change(function(){
  var twidth = livesyntaxhighlight.cmwidth;
  editor.setSize(twidth, this.options[this.selectedIndex].value*13);
});