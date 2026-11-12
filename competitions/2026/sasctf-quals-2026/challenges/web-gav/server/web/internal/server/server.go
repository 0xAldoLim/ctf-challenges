package server

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"strconv"
	"strings"
	"task/internal/config"
	"task/internal/database"
	"task/internal/waf"

	corazaHttp "github.com/corazawaf/coraza/v3/http"
)

const (
	defaultLat          = 55.751244
	defaultLon          = 37.618423
	defaultRadiusMeters = 12000
)

type Server struct {
	db      *database.DatabaseEngine
	cfg     *config.Config
	httpSrv *http.Server
}

func (srv *Server) indexHandler(w http.ResponseWriter, req *http.Request) {
	if req.URL.Path != "/" {
		http.NotFound(w, req)
		return
	}

	page, err := staticFiles.ReadFile("static/index.html")
	if err != nil {
		http.Error(w, "index page is not available", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write(page)
}

func (srv *Server) nearbyHandler(w http.ResponseWriter, req *http.Request) {
	lat, err := floatParam(req, "lat", defaultLat, -90, 90)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	lon, err := floatParam(req, "lon", defaultLon, -180, 180)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	radius, err := floatParam(req, "radius", defaultRadiusMeters, 500, 25000)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, err.Error())
		return
	}

	zone := strings.TrimSpace(req.URL.Query().Get("zone"))
	dashboard, err := srv.db.Dashboard(lat, lon, int(math.Round(radius)), zone)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "failed to build dashboard")
		return
	}

	writeJSON(w, http.StatusOK, dashboard)
}

func (srv *Server) chipHandler(w http.ResponseWriter, req *http.Request) {
	chipID := strings.TrimSpace(req.URL.Query().Get("chip"))
	if chipID == "" {
		writeJSONError(w, http.StatusBadRequest, "chip is required")
		return
	}

	pulse := strings.TrimSpace(req.URL.Query().Get("pulse"))
	report, err := srv.db.DogReport(chipID, pulse)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "failed to load chip report")
		return
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(report))
}

func (srv *Server) healthHandler(w http.ResponseWriter, req *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("ok"))
}

func (srv *Server) Run() error {
	return srv.httpSrv.ListenAndServe()
}

func (srv *Server) Shutdown(ctx context.Context) error {
	return srv.httpSrv.Shutdown(ctx)
}

func Init(logger *slog.Logger, cfg *config.Config) (*Server, error) {
	db, err := database.Init(cfg)
	if err != nil {
		return nil, fmt.Errorf("failed to init database: %w", err)
	}

	waf, err := waf.Init()
	if err != nil {
		return nil, fmt.Errorf("failed to init waf: %w", err)
	}

	srv := &Server{
		db:  db,
		cfg: cfg,
	}

	mux := http.NewServeMux()
	mux.Handle("/static/", http.StripPrefix("/static/", staticFileServer()))
	mux.HandleFunc("/api/nearby", srv.nearbyHandler)
	mux.HandleFunc("/api/chip", srv.chipHandler)
	mux.HandleFunc("/healthz", srv.healthHandler)
	mux.HandleFunc("/", srv.indexHandler)

	handler := corazaHttp.WrapHandler(waf, mux)
	srv.httpSrv = &http.Server{
		Addr:    fmt.Sprintf(":%s", cfg.Server.Port),
		Handler: handler,
	}

	logger.Info("web routes mounted", "routes", "static,/api/nearby,/api/chip,/healthz")
	return srv, nil
}

func floatParam(req *http.Request, name string, fallback, minValue, maxValue float64) (float64, error) {
	value := strings.TrimSpace(req.URL.Query().Get(name))
	if value == "" {
		return fallback, nil
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf("%s must be a number", name)
	}

	if parsed < minValue || parsed > maxValue {
		return 0, fmt.Errorf("%s must be between %.0f and %.0f", name, minValue, maxValue)
	}

	return parsed, nil
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		http.Error(w, "failed to encode response", http.StatusInternalServerError)
	}
}

func writeJSONError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{
		"error": message,
	})
}
