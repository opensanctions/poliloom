import nextPlugin from 'eslint-config-next'

const eslintConfig = [
  {
    ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts'],
  },
  ...nextPlugin,
]

export default eslintConfig
