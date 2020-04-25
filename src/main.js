// CREDITS TO https://www.cssscript.com/image-zoom-pan-hover-detail-view/
var addZoom = function (container) {
  // FETCH CONTAINER + IMAGE
  var imgsrc = container.currentStyle || window.getComputedStyle(container, false);
  var imgsrc = imgsrc.backgroundImage.slice(4, -1).replace(/"/g, "");
  var img = new Image();

  // LOAD IMAGE + ATTACH ZOOM
  img.src = imgsrc;
  img.onload = function () {
    var imgWidth = img.naturalWidth,
      imgHeight = img.naturalHeight,
      ratio = imgHeight / imgWidth,
      percentage = ratio * 100 + '%';

    // ZOOM ON MOUSE MOVE
    container.onmousemove = function (e) {
      var boxWidth = container.clientWidth,
        xPos = e.pageX - this.offsetLeft,
        yPos = e.pageY - this.offsetTop,
        xPercent = xPos / (boxWidth / 100) + '%',
        yPercent = yPos / (boxWidth * ratio / 100) + '%';

      Object.assign(container.style, {
        backgroundPosition: xPercent + ' ' + yPercent,
        backgroundSize: imgWidth + 'px'
      });
    };

    // RESET ON MOUSE LEAVE
    // container.onmouseleave = function (e) {
    //   Object.assign(container.style, {
    //     backgroundPosition: 'center',
    //     backgroundSize: 'cover'
    //   });
    // };
  }
};

var container = document.getElementById('zoomImg');
var isActive = false;

container.addEventListener('click', function () {
  if (!isActive) {
    isActive = true;
    Object.assign(container.style, {
      width: '200vw'
    });
  } else {
    isActive = false;
    console.log(container.style.width);
    Object.assign(container.style, {
      width: '100vw'
    });
  }
});