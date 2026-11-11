/**
 * Arable Atlas - Main Controller
 * Handles global UI interactions, interactive mapping, and soil analysis dashboard.
 */

document.addEventListener("DOMContentLoaded", function() {
    const mapElement = document.getElementById('map');
    if (!mapElement) return;

    // Initialize Map centered on Southern Africa region
    const map = L.map('map').setView([-19.0154, 29.1549], 6);
    let selectedLat, selectedLon;
    let currentMarker = null;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    function updateLocation(lat, lon, name = "Selected Location") {
        selectedLat = lat;
        selectedLon = lon;
        
        if (currentMarker) {
            map.removeLayer(currentMarker);
        }
        
        currentMarker = L.marker([lat, lon]).addTo(map)
            .bindPopup(`<b>${name}</b>`)
            .openPopup();
        
        map.setView([lat, lon], 12);
    }

    // Geolocation Handling
    const getLocationBtn = document.getElementById("getLocation");
    if (getLocationBtn) {
        getLocationBtn.addEventListener("click", function() {
            if (!navigator.geolocation) {
                alert("Geolocation is not supported by your browser.");
                return;
            }
            
            getLocationBtn.disabled = true;
            getLocationBtn.innerHTML = "<i class='bx bx-loader-alt bx-spin me-1'></i> Finding...";
            
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    console.log("Geolocated:", lat, lon);
                    updateLocation(lat, lon, "Your Location");
                    getLocationBtn.disabled = false;
                    getLocationBtn.innerHTML = "<i class='bx bx-current-location me-1'></i> Find Me";
                }, 
                function(error) {
                    console.error("Geolocation Error:", error);
                    alert("Error getting location: " + error.message);
                    getLocationBtn.disabled = false;
                    getLocationBtn.innerHTML = "<i class='bx bx-current-location me-1'></i> Find Me";
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        });
    }

    // Map Click Handling
    map.on('click', function(e) {
        updateLocation(e.latlng.lat, e.latlng.lng);
    });

    // Soil Analysis: Point Selection
    const processBtn = document.getElementById("processAnalysis");
    if (processBtn) {
        processBtn.addEventListener("click", function() {
            console.log("Process button clicked. Lat:", selectedLat, "Lon:", selectedLon);
            if (!selectedLat || !selectedLon) {
                alert("Please select a location on the map first.");
                return;
            }

            const loader = document.getElementById("loader");
            const cropEl = document.getElementById("cropsText");
            
            if (loader) loader.style.display = "block";
            if (cropEl) cropEl.textContent = "Fetching precision data...";

            console.log("Fetching /process with payload:", JSON.stringify({ lat: selectedLat, lon: selectedLon }));

            fetch("/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lat: selectedLat, lon: selectedLon })
            })
            .then(response => {
                console.log("Response received:", response);
                return response.json();
            })
            .then(data => {
                console.log("Data received:", data);
                if (loader) loader.style.display = "none";
                updateResultsUI(data);
            })
            .catch(error => {
                console.error("Processing Error:", error);
                if (loader) loader.style.display = "none";
                if (cropEl) cropEl.textContent = "Error fetching crop data. Please try again.";
            });
        });
    }

    // Soil Analysis: Image Upload
    const uploadForm = document.getElementById("uploadForm");
    const fileInput = document.getElementById("fileInput");
    if (uploadForm && fileInput) {
        uploadForm.addEventListener("submit", function(event) {
            event.preventDefault();
            if (!fileInput.files[0]) return;

            const formData = new FormData();
            formData.append("image", fileInput.files[0]);

            const loader = document.getElementById("loader");
            if (loader) loader.style.display = "block";

            fetch("/upload", {
                method: "POST",
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (loader) loader.style.display = "none";
                if (data.error) {
                    alert(data.error);
                    return;
                }

                updateLocation(data.latitude, data.longitude, data.location);
                updateResultsUI(data);
            })
            .catch(error => {
                if (loader) loader.style.display = "none";
                console.error("Upload Error:", error);
                alert("Failed to upload image. Ensure it contains GPS data.");
            });
        });
    }

    /**
     * Updates the Results UI with data received from the server.
     */
    function updateResultsUI(data) {
        const ids = ["latitude", "longitude", "soilType", "phLevel", "moisture", "nitrogen", "clay", "sand", "silt"];
        
        // Handle direct ID mapping
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                // Map phLevel -> ph, etc.
                let key = id.replace("Level", "").replace("Type", "_type").replace("Content", "");
                // Special mapping
                if (id === "soilType") key = "soil_type";
                
                let val = data[id] || data[key] || data[key.toLowerCase()];
                el.textContent = val || "-";
            }
        });

        // Explicitly handle locationName
        const locEl = document.getElementById("locationName");
        if (locEl) {
            locEl.textContent = data.location || "Location Unavailable";
        }

        const cropEl = document.getElementById("cropsText");
        if (cropEl) {
            cropEl.style.opacity = 0;
            setTimeout(() => {
                cropEl.textContent = data.actionable_advice || "No specific advice available.";
                cropEl.style.opacity = 1;
            }, 300);
        }
    }
});
