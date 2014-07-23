jQuery(document).bind('DOMSubtreeModified', function (){
                            $( "#field-cc" ).autocomplete({
                                source: "user_list",
                                multiple: true,
                                formatItem: formatItem,
                                delay: 100
                            });
                        });
