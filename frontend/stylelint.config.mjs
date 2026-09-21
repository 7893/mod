/** @type {import('stylelint').Config} */
export default {
  extends: ['stylelint-config-recommended'],
  ignoreFiles: ['dist/**', 'node_modules/**', 'output/**', 'releases/**'],
  overrides: [
    {
      files: ['**/*.vue'],
      customSyntax: 'postcss-html',
    },
  ],
  rules: {
    'at-rule-no-unknown': [true, { ignoreAtRules: ['reference', 'theme'] }],
    // Tailwind v4 expands --spacing() at build time; Stylelint's CSS grammar
    // intentionally does not know this framework function.
    'declaration-property-value-no-unknown': null,
    // Component variants deliberately override their base block later in the
    // cascade; selector ordering is a project contract, not an error here.
    'no-descending-specificity': null,
  },
}
