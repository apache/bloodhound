jQuery(document).bind('DOMSubtreeModified', function (){

                            $( "#field-reporter" ).autocomplete({
                                source: "user_list",
                                formatItem: formatItem
                            });
                        });

