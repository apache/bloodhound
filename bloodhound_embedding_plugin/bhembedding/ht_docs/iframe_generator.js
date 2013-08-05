function makeIFrame(src)
{
   var iframe = document.createElement('iframe');
   iframe.setAttribute("src", src);
   iframe.style.width = 500+"px";
   iframe.style.height = 500+"px";
   document.body.appendChild(iframe);
}
