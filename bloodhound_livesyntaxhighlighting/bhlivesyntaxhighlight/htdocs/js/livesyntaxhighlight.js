//Defining a class for livesyntaxhighlight related stuff.
livesyntaxhighlight = {
  twidth : "",
  theight : "",
  cmwidth : "",
  cmheight : "",
  editor : null,
  //Initializing function
  init : function () {
    //caching the object to improve performance
    var textobj = $('#text');
    livesyntaxhighlight.twidth = textobj.width();
    livesyntaxhighlight.theight = textobj.height();
    livesyntaxhighlight.editor = CodeMirror.fromTextArea(
      document.getElementById("text"), {
        lineNumbers: true,
        matchBrackets: true,
        lineWrapping: true,
        continueComments: "Enter",
        extraKeys: {"Ctrl-Q": "toggleComment"}
      });
    console.log(textobj.width() + ' '+ textobj.height());
    livesyntaxhighlight.resizeCodeMirror();
    livesyntaxhighlight.editor.refresh();
    $(window).resize(livesyntaxhighlight.resizeCodeMirror);
  },
  resizeCodeMirror : function (){
    var textobj = $('#text');
    var spanwidth = $('.span12').width()/2 - 15;
    var sidebyside = document.getElementById('sidebyside');
    console.log(textobj.width() + ' '+ textobj.height());
    cmwidth = livesyntaxhighlight.twidth;
    if ($('.span12').width() > 688 && sidebyside.checked)
      cmwidth = spanwidth;
    else cmwidth = 2 * (spanwidth +15);
    cmheight = textobj.height();
    // if(document.getElementById('preview'))
    //   cmheight = $('#preview').height();
    // livesyntaxhighlight.editor.setSize(cmwidth, cmheight);
    livesyntaxhighlight.editor.refresh();
  },
  //Function for the wikitoolbar processing
  encloseSelection: function (prefix, suffix) {
    var editor = livesyntaxhighlight.editor;
    editor.focus();
    var oldsel = editor.getSelection();
    editor.replaceSelection(prefix + oldsel + suffix);
  }
};
// Invoked initially to initialize the editor
$(document).ready(function (){
  livesyntaxhighlight.init();
  // To adjust the height of the editor
  $("#editrows").change(function(){
    var twidth = livesyntaxhighlight.cmwidth;
    livesyntaxhighlight.editor.setSize(twidth, 
      this.options[this.selectedIndex].value*13);
  });
  //Functions to hook in the wikitoolbar
  $("#strong").click(function () {
    livesyntaxhighlight.encloseSelection("'''", "'''");
  });
  $("#em").click(function () {
    livesyntaxhighlight.encloseSelection("''", "''");
  });
  $("#heading").click(function () {
    livesyntaxhighlight.encloseSelection("\n== ", " ==\n");
  });
  $("#link").click(function () {
    livesyntaxhighlight.encloseSelection("[", "]");
  });
  $("#code").click(function () {
    livesyntaxhighlight.encloseSelection("\n{{{\n", "\n}}}\n");
  });
  $("#hr").click(function () {
    livesyntaxhighlight.encloseSelection("\n----\n", "");
  });
  $("#np").click(function () {
    livesyntaxhighlight.encloseSelection("\n\n", "");
  });
  $("#br").click(function () {
    livesyntaxhighlight.encloseSelection("[[BR]]\n", "");
  });
  $("#img").click(function () {
    livesyntaxhighlight.encloseSelection("[[Image(", ")]]");
  });
});
