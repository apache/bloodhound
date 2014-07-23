jQuery(document).ready(function ($) {
                          function addAutocompleteBehavior() {
                            var filters = $('#filters');
                            var contains = function (container, contained) {
                              while (contained !== null) {
                                if (container === contained)
                                  return true;
                                contained = contained.parentNode;
                              }
                              return false;
                            };
                            var listener = function (event) {
                              var target = event.target || event.srcElement;
                              filters.each(function () {
                                if (contains(this, target)) {
                                  var input = $(this).find('input:text').filter(function () {
                                    return target === this;
                                  });
                                  var name = input.attr('name');
                                  if (input.attr('autocomplete') !== 'off' &&
                                    /^(?:[0-9]+_)?(?:keywords)$/.test(name)) {
                                    input.tagsinput({
                                        typeahead: {
                                            source: keywords
                                            }
                                        });
                                  }
                                }
                              });
                            };
                            if ($.fn.on) {
                              // delegate method is available in jQuery 1.7+
                              filters.on('focusin', 'input:text', listener);
                            }
                            else if (window.addEventListener) {
                              // use capture=true cause focus event doesn't bubble in the default
                              filters.each(function () {
                                this.addEventListener('focus', listener, true);
                              });
                            }
                            else {
                              // focusin event bubbles, the event is avialable for IE only
                              filters.each(function () {
                                this.attachEvent('onfocusin', listener);
                              });
                            }
                          }
                          addAutocompleteBehavior();
                });
