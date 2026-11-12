const bounds = {
  minLon: 37.52,
  maxLon: 37.76,
  minLat: 55.66,
  maxLat: 55.86,
};

const viewBox = { width: 1000, height: 620 };

const state = {
  dogs: [],
};

const latInput = document.querySelector("#latInput");
const lonInput = document.querySelector("#lonInput");
const radiusInput = document.querySelector("#radiusInput");
const radiusValue = document.querySelector("#radiusValue");
const zoneSelect = document.querySelector("#zoneSelect");
const refreshButton = document.querySelector("#refreshButton");
const chipForm = document.querySelector("#chipForm");
const chipInput = document.querySelector("#chipInput");
const chipReport = document.querySelector("#chipReport");
const metrics = document.querySelector("#metrics");
const resultCount = document.querySelector("#resultCount");
const geoLayer = document.querySelector("#geoLayer");
const markerLayer = document.querySelector("#markerLayer");
const originMarker = document.querySelector("#originMarker");
const dogList = document.querySelector("#dogList");

radiusInput.addEventListener("input", () => {
  radiusValue.textContent = radiusInput.value;
});

refreshButton.addEventListener("click", () => loadDashboard());
zoneSelect.addEventListener("change", () => loadDashboard());

chipForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const chip = chipInput.value.trim();
  if (!chip) return;

  chipReport.classList.add("is-visible");
  chipReport.textContent = "Loading...";

  try {
    const response = await fetch(`/api/chip?chip=${encodeURIComponent(chip)}`);
    const report = await response.json();
    if (!response.ok) throw new Error(report.error || "chip request failed");
    renderReport(report);

    if (report.found) {
      latInput.value = Number(report.lat).toFixed(6);
      lonInput.value = Number(report.lon).toFixed(6);
      await loadDashboard();
      focusDog(report.chip_id);
    }
  } catch (error) {
    chipReport.innerHTML = `<h2>Error</h2><p>${escapeHTML(error.message)}</p>`;
  }
});

function project(lon, lat) {
  const x = ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * viewBox.width;
  const y = ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * viewBox.height;
  return {
    x: clamp(x, 0, viewBox.width),
    y: clamp(y, 0, viewBox.height),
    xp: clamp((x / viewBox.width) * 100, 0, 100),
    yp: clamp((y / viewBox.height) * 100, 0, 100),
  };
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

async function loadDashboard() {
  const params = new URLSearchParams({
    lat: latInput.value,
    lon: lonInput.value,
    radius: radiusInput.value,
    zone: zoneSelect.value,
  });

  const response = await fetch(`/api/nearby?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    renderError(payload.error || "Could not refresh the map");
    return;
  }

  state.dogs = payload.dogs || [];
  renderZoneSelect(payload.zones || []);
  renderMetrics(payload.metrics);
  renderMap(payload);
  renderDogList(state.dogs);
}

function renderZoneSelect(zones) {
  const current = zoneSelect.value;
  zoneSelect.innerHTML = '<option value="">All zones</option>';

  for (const zone of zones) {
    const option = document.createElement("option");
    option.value = zone.slug;
    option.textContent = zone.name;
    zoneSelect.appendChild(option);
  }

  if (zones.some((zone) => zone.slug === current)) {
    zoneSelect.value = current;
  }
}

function renderMetrics(data) {
  const items = [
    ["Total", data.total_dogs],
    ["Moving", data.moving_dogs],
    ["Stationary", data.quiet_dogs],
    ["Signal lost", data.lost_signal_dogs],
  ];

  metrics.innerHTML = items
    .map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderMap(payload) {
  geoLayer.replaceChildren();
  markerLayer.replaceChildren();

  for (const zone of payload.zones || []) {
    drawZone(zone);
  }

  for (const dog of state.dogs) {
    drawRoute(dog);
  }

  const origin = project(payload.origin.lon, payload.origin.lat);
  originMarker.style.left = `${origin.xp}%`;
  originMarker.style.top = `${origin.yp}%`;

  for (const dog of state.dogs) {
    drawMarker(dog);
  }

  resultCount.textContent = `${state.dogs.length} ${pluralDogs(state.dogs.length)}`;
}

function drawZone(zone) {
  const geometry = parseGeoJSON(zone.boundary_geojson);
  if (!geometry || !geometry.coordinates || !geometry.coordinates[0]) return;

  const points = geometry.coordinates[0]
    .map(([lon, lat]) => {
      const point = project(lon, lat);
      return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
    })
    .join(" ");

  const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  polygon.setAttribute("class", "zone-shape");
  polygon.setAttribute("points", points);
  geoLayer.appendChild(polygon);

  const labelPoint = project(zone.center_lon, zone.center_lat);
  const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
  label.setAttribute("class", "zone-label");
  label.setAttribute("x", labelPoint.x.toFixed(1));
  label.setAttribute("y", labelPoint.y.toFixed(1));
  label.textContent = zone.name;
  geoLayer.appendChild(label);
}

function drawRoute(dog) {
  const geometry = parseGeoJSON(dog.route_geojson);
  if (!geometry || !geometry.coordinates) return;

  const points = geometry.coordinates
    .map(([lon, lat]) => {
      const point = project(lon, lat);
      return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
    })
    .join(" ");

  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("class", "route-line");
  line.setAttribute("points", points);
  geoLayer.appendChild(line);

  const snap = parseGeoJSON(dog.closest_route_point_geojson);
  if (snap && snap.coordinates) {
    const point = project(snap.coordinates[0], snap.coordinates[1]);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "route-snap");
    circle.setAttribute("cx", point.x.toFixed(1));
    circle.setAttribute("cy", point.y.toFixed(1));
    circle.setAttribute("r", "6");
    geoLayer.appendChild(circle);
  }
}

function drawMarker(dog) {
  const point = project(dog.lon, dog.lat);
  const marker = document.createElement("button");
  marker.type = "button";
  marker.className = `marker ${statusClass(dog.status)}`;
  marker.dataset.chip = dog.chip_id;
  marker.setAttribute("aria-label", `${dog.name}, ${dog.status}, ${formatDistance(dog.distance_meters)}`);
  marker.style.left = `${point.xp}%`;
  marker.style.top = `${point.yp}%`;
  marker.innerHTML = `
    <span class="marker-pin"></span>
    <span class="marker-tooltip">
      <strong>${escapeHTML(dog.name)}</strong>
      ${formatDistance(dog.distance_meters)}
    </span>
  `;
  marker.addEventListener("click", () => focusDog(dog.chip_id));
  markerLayer.appendChild(marker);
}

function renderDogList(dogs) {
  if (dogs.length === 0) {
    dogList.innerHTML = '<div class="empty-state">No dogs in this radius</div>';
    return;
  }

  dogList.innerHTML = dogs
    .map((dog) => {
      const status = statusClass(dog.status);
      return `
        <article class="dog-card" id="dog-${escapeHTML(dog.chip_id)}">
          <header>
            <div>
              <h2>${escapeHTML(dog.name)}</h2>
              <p>${escapeHTML(dog.chip_id)} · ${escapeHTML(dog.breed)}</p>
            </div>
            <span class="status-pill ${status}">${escapeHTML(dog.status)}</span>
          </header>
          <div class="dog-facts">
            <div><span>Distance</span><strong>${formatDistance(dog.distance_meters)}</strong></div>
            <div><span>Battery</span><strong>${dog.battery}%</strong></div>
            <div><span>Route</span><strong>${dog.route_kilometers} km</strong></div>
            <div><span>Zone</span><strong>${escapeHTML(dog.zone_name)}</strong></div>
          </div>
          <p>${escapeHTML(dog.handler_hint)}</p>
        </article>
      `;
    })
    .join("");
}

function renderReport(report) {
  chipReport.classList.add("is-visible");
  if (!report.found) {
    chipReport.innerHTML = "<h2>Chip not found</h2><p>Check the ID and try again.</p>";
    return;
  }

  chipReport.innerHTML = `
    <h2>${escapeHTML(report.name)} · ${escapeHTML(report.chip_id)}</h2>
    <p>${escapeHTML(report.zone)} · ${formatDistance(report.distance_to_center_meters)} from center</p>
    <p>${escapeHTML(report.status)} · battery ${report.battery}% · ${report.route_kilometers} km</p>
  `;
}

function renderError(message) {
  resultCount.textContent = "Error";
  dogList.innerHTML = `<div class="empty-state">${escapeHTML(message)}</div>`;
}

function focusDog(chipID) {
  const card = document.getElementById(`dog-${chipID}`);
  if (card) {
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.animate(
      [
        { outlineColor: "rgba(46, 111, 163, 0)" },
        { outlineColor: "rgba(46, 111, 163, 0.7)" },
        { outlineColor: "rgba(46, 111, 163, 0)" },
      ],
      { duration: 900, iterations: 1 }
    );
  }
}

function parseGeoJSON(value) {
  if (!value) return null;
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function statusClass(status) {
  if (status.includes("lost")) return "lost";
  if (status.includes("stationary")) return "idle";
  return "moving";
}

function formatDistance(meters) {
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)} km`;
  return `${meters} m`;
}

function pluralDogs(count) {
  return count === 1 ? "dog" : "dogs";
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadDashboard().catch((error) => renderError(error.message));
