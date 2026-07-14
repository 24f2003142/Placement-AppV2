const { createApp } = Vue;

createApp({
    data() {
        return {
            formData: {
                email: '',
                password: ''
            },
            submitting: false,
            errorMessage: ''
        };
    },
    methods: {
        async submitForm() {
            this.errorMessage = '';
            this.submitting = true;

            const form = this.$refs.form;
            const formData = new FormData(form);

            try {
                const response = await fetch(window.loginConfig.loginUrl, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: new URLSearchParams(formData)
                });

                const data = await response.json().catch(() => null);

                if (!response.ok) {
                    throw new Error(data?.message || 'Login failed');
                }

                if (data?.redirect) {
                    window.location.href = data.redirect;
                    return;
                }

                window.location.reload();
            } catch (error) {
                this.errorMessage = error.message || 'Login failed';
            } finally {
                this.submitting = false;
            }
        }
    }
}).mount('#login-app');
