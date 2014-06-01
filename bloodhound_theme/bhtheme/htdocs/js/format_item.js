function formatItem(row) {
  var firstLine = (row[2]) ? row[0] + " (" + row[2] + ")" : row[0];
  return "<div class=\"name\">" + firstLine + "</div>"
    + (row[1] ? "<div class=\"mail\">" + row[1] + "</div>" : '');
}
