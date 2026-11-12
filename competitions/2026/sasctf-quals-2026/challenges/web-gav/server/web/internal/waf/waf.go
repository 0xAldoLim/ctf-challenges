package waf

import (
	"github.com/corazawaf/coraza/v3"
)

func Init() (coraza.WAF, error) {
	waf, err := coraza.NewWAF(
		coraza.NewWAFConfig().
			WithDirectives(directives),
	)
	if err != nil {
		return nil, err
	}
	return waf, nil
}
