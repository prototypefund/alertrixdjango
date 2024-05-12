function update_advanced_fields_visibility() {
    var show_advanced_input = document.getElementById('show-advanced-input-fields');
    console.log(show_advanced_input);
    if (!show_advanced_input.checked) { var display = "none"; }
    inputs = document.getElementsByClassName('advanced');
    if (inputs.length > 0) {
        show_advanced_input.parentNode.style.removeProperty('display');
        for (var i = 0; i < inputs.length; i++) {
            var inp = inputs.item(i);
            if (inp.parentNode.getElementsByClassName('errorlist').length == 0) {
                if (show_advanced_input.checked) {
                    inp.parentNode.parentNode.style.removeProperty('display');
                }
                else {
                    inp.parentNode.parentNode.style.display = display;
                }
            }
        }
    }
    else {
        show_advanced_input.parentNode.style.display = display;
    }
}

window.onload = function() {
    update_advanced_fields_visibility();
    document.getElementById('show-advanced-input-fields').addEventListener('click', function() {update_advanced_fields_visibility();});
}
