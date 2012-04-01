
var FORWARD = 0.9;
var BACK = -0.9;
function move(target, direction) {
  target = jQuery(target);
  var pos = parseInt(target.css('marginLeft'), 10);
  var tw = target.width();
  var pw = target.parent().width();
  var x = 0;
  if (tw >= pw) {
    x = pos + direction * pw;
    if (x > 0)
      x = 0;
    else {
      var last = target.find('.last');
      var ll = last.offset().left;
      var lw = last.width();
      if (ll + lw <= pw && direction < 0)
        x = pos;
      else if (ll < pw && direction < 0)
        x = pos - lw;
    }
  }
  target.animate({marginLeft: x}, 'slow');
}

