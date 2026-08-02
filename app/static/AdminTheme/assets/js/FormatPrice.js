function formatPrice(input) {
    var value = input.value.replace(/,/g, ''); // Remove existing commas
    let dotCount = (input.value.match(/\./g) || []).length;
    // If more than one dot is present, prevent further typing of dots
    if (dotCount > 1) {
        value = value.slice(0, -1); // Remove the last character
    }
    var parts = value.split('.'); // Split into integer and decimal parts
    parts[0] = parts[0].replace(/\D/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ','); // Add commas to integer part
    input.value = parts.join('.'); // Join integer and decimal parts back together
}